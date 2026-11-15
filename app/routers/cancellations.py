
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import (
    Booking,
    Payment,
    Ticket,
    TicketCategory,
    Event
)
from app.security.dependencies import require_attendee, require_admin
from app.security.csrf import verify_csrf_token


router = APIRouter(
    prefix="/api/cancellations",
    tags=["Cancellations and Refunds"]
)


def normalize_datetime(value):
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def calculate_refund(amount, event_start):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = normalize_datetime(event_start)

    hours_remaining = (start - now).total_seconds() / 3600

    if hours_remaining > 48:
        percentage = 1.0
    elif hours_remaining >= 24:
        percentage = 0.5
    else:
        percentage = 0.0

    return round(float(amount) * percentage, 2), percentage


def cancel_booking_records(db, booking, refund_amount):
    """Update payment, booking, ticket and inventory records."""

    payment = db.query(Payment).filter(
        Payment.booking_id == booking.id
    ).first()

    if not payment:
        raise HTTPException(
            status_code=409,
            detail="Payment record not found for this booking"
        )

    category = db.query(TicketCategory).filter(
        TicketCategory.id == booking.ticket_category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found"
        )

    # Release the seats allocated to this booking.
    if category.sold_quantity < booking.quantity:
        raise HTTPException(
            status_code=409,
            detail="Ticket inventory is inconsistent; cancellation stopped"
        )

    category.sold_quantity -= booking.quantity

    # Invalidate every ticket belonging to this booking.
    tickets = db.query(Ticket).filter(
        Ticket.booking_id == booking.id
    ).all()

    for ticket in tickets:
        ticket.status = "cancelled"

    booking.status = "cancelled"

    payment.amount = refund_amount
    payment.status = "refunded"

    return len(tickets)


@router.post(
    "/booking/{booking_id}",
    dependencies=[Depends(verify_csrf_token)]
)
def cancel_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == current_user.id
    ).with_for_update().first()

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail="Only confirmed bookings can be cancelled"
        )

    event = db.query(Event).filter(
        Event.id == booking.event_id
    ).first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="This event has already been cancelled"
        )

    if datetime.now(timezone.utc).replace(tzinfo=None) >= normalize_datetime(event.start_time):
        raise HTTPException(
            status_code=400,
            detail="Bookings cannot be cancelled after the event has started"
        )

    refund_amount, refund_percentage = calculate_refund(
        booking.total_amount,
        event.start_time
    )

    try:
        ticket_count = cancel_booking_records(
            db,
            booking,
            refund_amount
        )

        db.commit()

        return {
            "message": "Booking cancelled successfully",
            "booking_id": booking.id,
            "booking_status": booking.status,
            "original_amount": booking.total_amount,
            "refund_percentage": int(refund_percentage * 100),
            "refund_amount": refund_amount,
            "payment_status": "refunded",
            "tickets_cancelled": ticket_count,
            "refund_policy": (
                "More than 48 hours: 100%; "
                "24 to 48 hours: 50%; "
                "less than 24 hours: 0%"
            )
        }

    except Exception:
        db.rollback()
        raise


@router.post(
    "/event/{event_id}",
    dependencies=[Depends(verify_csrf_token)]
)
def cancel_event_and_refund(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):

    event = db.query(Event).filter(
        Event.id == event_id
    ).with_for_update().first()

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Event is already cancelled"
        )

    try:
        bookings = db.query(Booking).filter(
            Booking.event_id == event_id,
            Booking.status == "confirmed"
        ).with_for_update().all()

        total_refund = 0.0
        cancelled_bookings = 0
        cancelled_tickets = 0

        for booking in bookings:
            payment = db.query(Payment).filter(
                Payment.booking_id == booking.id
            ).first()

            if not payment:
                raise HTTPException(
                    status_code=409,
                    detail=f"Payment record missing for booking {booking.id}"
                )

            refund_amount = float(booking.total_amount)

            cancelled_tickets += cancel_booking_records(
                db,
                booking,
                refund_amount
            )

            total_refund += refund_amount
            cancelled_bookings += 1

        event.status = "cancelled"

        db.commit()

        return {
            "message": "Event cancelled and full refunds processed",
            "event_id": event.id,
            "event_status": event.status,
            "cancelled_bookings": cancelled_bookings,
            "cancelled_tickets": cancelled_tickets,
            "total_refund": round(total_refund, 2),
            "refund_percentage": 100
        }

    except Exception:
        db.rollback()
        raise
