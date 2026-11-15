
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.database.connection import get_db
from app.models.entities import (
    Booking,
    Payment,
    TicketCategory,
    User
)
from app.schemas.booking import BookingCreate
from app.security.dependencies import require_attendee
from app.security.csrf import verify_csrf_token
from app.agents.booking_agent import handle_booking_request
from app.agents.message_bus import create_message


router = APIRouter(
    prefix="/api/bookings",
    tags=["Ticket Booking"]
)


# --------------------------------------------------
# 1. CREATE BOOKING
# Attendee only
# --------------------------------------------------

@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(verify_csrf_token)]
)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_attendee)
):

    # Create a conversation ID for agent communication.
    conversation_id = str(uuid.uuid4())

    # Send a booking REQUEST to BookingAgent.
    message = {
        "sender": "BookingAPI",
        "receiver": "BookingAgent",
        "performative": "REQUEST",
        "content": {
            "event_id": data.event_id,
            "ticket_category_id": data.ticket_category_id,
            "quantity": data.quantity
        },
        "conversation_id": conversation_id
    }

    # BookingAgent makes the booking decision.
    agent_response = handle_booking_request(db, message)

    if agent_response["performative"] != "AGREE":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "BookingAgent refused the request.",
                "reason": agent_response["content"]
            }
        )

    # Get the selected ticket category.
    category = (
        db.query(TicketCategory)
        .filter(
            TicketCategory.id == data.ticket_category_id,
            TicketCategory.event_id == data.event_id
        )
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found."
        )

    # Calculate the booking amount.
    total_amount = category.price * data.quantity

    try:
        # Atomically allocate tickets.
        # This prevents two simultaneous requests from
        # selling more tickets than the category contains.
        allocation = db.execute(
            update(TicketCategory)
            .where(
                TicketCategory.id == data.ticket_category_id,
                TicketCategory.event_id == data.event_id,
                TicketCategory.sold_quantity + data.quantity
                <= TicketCategory.quantity
            )
            .values(
                sold_quantity=(
                    TicketCategory.sold_quantity + data.quantity
                )
            )
            .execution_options(synchronize_session=False)
        )

        if allocation.rowcount != 1:
            db.rollback()

            create_message(
                db=db,
                sender="BookingAgent",
                receiver="BookingAPI",
                performative="REFUSE",
                content={
                    "reason": "Tickets were sold before allocation could be completed.",
                    "requested_quantity": data.quantity
                },
                conversation_id=conversation_id
            )

            raise HTTPException(
                status_code=409,
                detail="Sorry, these tickets are no longer available."
            )

        # Create the booking record.
        new_booking = Booking(
            user_id=current_user.id,
            event_id=data.event_id,
            ticket_category_id=data.ticket_category_id,
            quantity=data.quantity,
            total_amount=total_amount,
            status="confirmed"
        )

        db.add(new_booking)
        db.flush()

        # Generate a simulated payment reference.
        payment_reference = (
            "ES-" + secrets.token_hex(8).upper()
        )

        new_payment = Payment(
            booking_id=new_booking.id,
            payment_reference=payment_reference,
            amount=total_amount,
            status="simulated_success"
        )

        db.add(new_payment)

        db.commit()
        db.refresh(new_booking)

        return {
            "message": "Booking successful!",
            "booking": {
                "id": new_booking.id,
                "event_id": new_booking.event_id,
                "ticket_category_id": new_booking.ticket_category_id,
                "quantity": new_booking.quantity,
                "total_amount": new_booking.total_amount,
                "status": new_booking.status
            },
            "payment": {
                "payment_reference": payment_reference,
                "amount": total_amount,
                "status": "simulated_success"
            },
            "agent": {
                "name": "BookingAgent",
                "decision": "AGREE",
                "conversation_id": conversation_id
            }
        }

    except HTTPException:
        raise

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 2. VIEW MY BOOKING HISTORY
# Attendee only
# --------------------------------------------------

@router.get("/my-bookings")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_attendee)
):

    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.id.desc())
        .all()
    )

    results = []

    for booking in bookings:

        results.append({
            "booking_id": booking.id,
            "event_id": booking.event_id,
            "ticket_category_id": booking.ticket_category_id,
            "quantity": booking.quantity,
            "total_amount": booking.total_amount,
            "status": booking.status
        })

    return {
        "total_bookings": len(results),
        "bookings": results
    }
