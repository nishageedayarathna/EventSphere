
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import (
    Event,
    TicketCategory,
    WaitlistEntry,
    Booking,
    Payment
)
from app.security.dependencies import require_attendee
from app.security.csrf import verify_csrf_token

from app.agents.waitlist_agent import waitlist_agent
from app.agents.message_bus import create_message
from app.agents.ticket_agent import handle_ticket_request


router = APIRouter(
    prefix="/api/waitlist",
    tags=["Waitlist"]
)


# --------------------------------------------------
# 1. JOIN WAITLIST
# --------------------------------------------------

@router.post("/join")
def join_waitlist(
    event_id: int,
    ticket_category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee),
    csrf=Depends(verify_csrf_token)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.status == "published"
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Published event not found"
        )

    category = db.query(TicketCategory).filter(
        TicketCategory.id == ticket_category_id,
        TicketCategory.event_id == event_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found"
        )

    existing = db.query(WaitlistEntry).filter(
        WaitlistEntry.user_id == current_user.id,
        WaitlistEntry.event_id == event_id,
        WaitlistEntry.ticket_category_id == ticket_category_id,
        WaitlistEntry.status.in_(["waiting", "offered"])
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You are already on this waitlist"
        )

    available = category.quantity - category.sold_quantity

    if available > 0:
        raise HTTPException(
            status_code=400,
            detail="Tickets are still available. Please book directly."
        )

    entry = WaitlistEntry(
        user_id=current_user.id,
        event_id=event_id,
        ticket_category_id=ticket_category_id,
        status="waiting"
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "message": "You have joined the waitlist",
        "waitlist_entry_id": entry.id,
        "status": entry.status
    }


# --------------------------------------------------
# 2. VIEW MY WAITLIST ENTRIES
# --------------------------------------------------

@router.get("/my-entries")
def get_my_waitlist_entries(
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):
    entries = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.user_id == current_user.id)
        .order_by(WaitlistEntry.id.desc())
        .all()
    )

    return [
        {
            "id": entry.id,
            "event_id": entry.event_id,
            "ticket_category_id": entry.ticket_category_id,
            "status": entry.status,
            "hold_expires_at": entry.hold_expires_at
        }
        for entry in entries
    ]


# --------------------------------------------------
# 3. ACCEPT WAITLIST OFFER
# --------------------------------------------------

@router.post("/{entry_id}/accept")
def accept_waitlist_offer(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee),
    csrf=Depends(verify_csrf_token)
):
    entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.id == entry_id,
            WaitlistEntry.user_id == current_user.id
        )
        .with_for_update()
        .first()
    )

    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Waitlist entry not found"
        )

    if entry.status != "offered":
        raise HTTPException(
            status_code=400,
            detail="There is no active ticket offer for this entry"
        )

    expiry = entry.hold_expires_at

    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if not expiry or expiry <= datetime.now(timezone.utc):
        entry.status = "expired"
        entry.hold_expires_at = None
        db.commit()

        waitlist_agent.process_waitlist(
            db,
            entry.event_id,
            entry.ticket_category_id
        )

        raise HTTPException(
            status_code=400,
            detail="Your ticket offer has expired"
        )

    event = db.query(Event).filter(
        Event.id == entry.event_id,
        Event.status == "published"
    ).first()

    if not event:
        raise HTTPException(
            status_code=400,
            detail="The event is no longer available"
        )

    category = db.query(TicketCategory).filter(
        TicketCategory.id == entry.ticket_category_id,
        TicketCategory.event_id == entry.event_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=400,
            detail="Ticket category not found"
        )

    # Atomically reserve one ticket.
    inventory_result = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == category.id,
            TicketCategory.sold_quantity < TicketCategory.quantity
        )
        .values(
            sold_quantity=TicketCategory.sold_quantity + 1
        )
    )

    if inventory_result.rowcount != 1:
        entry.status = "waiting"
        entry.hold_expires_at = None
        db.commit()

        raise HTTPException(
            status_code=409,
            detail="The ticket is no longer available"
        )

    total_amount = category.price

    booking = Booking(
        user_id=current_user.id,
        event_id=event.id,
        ticket_category_id=category.id,
        quantity=1,
        total_amount=total_amount,
        status="confirmed"
    )

    db.add(booking)
    db.flush()

    payment_reference = f"ES-WL-{booking.id}-{current_user.id}"

    payment = Payment(
        booking_id=booking.id,
        payment_reference=payment_reference,
        amount=total_amount,
        status="simulated_success"
    )

    db.add(payment)

    entry.status = "accepted"
    entry.hold_expires_at = None

    try:
        db.commit()
        db.refresh(booking)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not complete the waitlist booking"
        )

    # Send a REQUEST message to TicketAgent.
    ticket_message = create_message(
        db=db,
        sender="WaitlistAgent",
        receiver="TicketAgent",
        performative="REQUEST",
        content={
            "booking_id": booking.id
        }
    )

    ticket_result = handle_ticket_request(
        db,
        ticket_message
    )

    if ticket_result.get("performative") != "AGREE":
        return {
            "message": "Booking created, but ticket generation needs attention",
            "booking_id": booking.id,
            "payment_reference": payment_reference,
            "ticket_agent_response": ticket_result
        }

    return {
        "message": "Waitlist offer accepted successfully",
        "booking_id": booking.id,
        "quantity": 1,
        "total_amount": total_amount,
        "payment_reference": payment_reference,
        "ticket_agent_response": ticket_result
    }


# --------------------------------------------------
# 4. DECLINE WAITLIST OFFER
# --------------------------------------------------

@router.post("/{entry_id}/decline")
def decline_waitlist_offer(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee),
    csrf=Depends(verify_csrf_token)
):
    entry = db.query(WaitlistEntry).filter(
        WaitlistEntry.id == entry_id,
        WaitlistEntry.user_id == current_user.id
    ).first()

    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Waitlist entry not found"
        )

    if entry.status != "offered":
        raise HTTPException(
            status_code=400,
            detail="There is no active offer to decline"
        )

    event_id = entry.event_id
    category_id = entry.ticket_category_id

    entry.status = "declined"
    entry.hold_expires_at = None

    db.commit()

    next_offer = waitlist_agent.process_waitlist(
        db,
        event_id,
        category_id
    )

    return {
        "message": "Ticket offer declined",
        "next_waitlist_result": next_offer
    }
