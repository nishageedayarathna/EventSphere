
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import (
    Booking,
    Payment,
    Ticket,
    TicketCategory,
    Event,
    WaitlistEntry
)
from app.security.dependencies import require_attendee, require_admin
from app.security.csrf import verify_csrf_token

from app.agents.waitlist_agent import waitlist_agent
from app.agents.message_bus import create_message, deliver_message


router = APIRouter(
    prefix="/api/cancellations",
    tags=["Cancellations and Refunds"]
)


# --------------------------------------------------
# DATETIME AND REFUND FUNCTIONS
# --------------------------------------------------

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


# --------------------------------------------------
# NOTIFICATIONAGENT INTEGRATION
# --------------------------------------------------

def notify_cancellation(
    db: Session,
    user_id: int,
    booking_id: int,
    event_id: int,
    message_text: str,
    conversation_id: str = None
):
    """
    Send an INFORM message to NotificationAgent
    and create a notification for the attendee.
    """

    notification_message = create_message(
        db=db,
        sender="CancellationAPI",
        receiver="NotificationAgent",
        performative="INFORM",
        content={
            "user_id": user_id,
            "title": "Booking Cancelled",
            "message": message_text,
            "booking_id": booking_id,
            "event_id": event_id
        },
        conversation_id=conversation_id
    )

    notification_response = deliver_message(
        db=db,
        message=notification_message
    )

    if notification_response.get("performative") != "AGREE":

        raise Exception(
            f"NotificationAgent rejected the message: "
            f"{notification_response}"
        )

    # Save notification and agent messages.
    db.commit()

    return notification_response


# --------------------------------------------------
# CANCEL BOOKING RECORDS
# --------------------------------------------------

def cancel_booking_records(db, booking, refund_amount):
    """
    Update payment, booking, tickets and ticket inventory.
    """

    payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=409,
            detail="Payment record not found for this booking"
        )

    category = (
        db.query(TicketCategory)
        .filter(TicketCategory.id == booking.ticket_category_id)
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Ticket category not found"
        )

    if category.sold_quantity < booking.quantity:
        raise HTTPException(
            status_code=409,
            detail="Ticket inventory is inconsistent; cancellation stopped"
        )

    # Release booked tickets.
    category.sold_quantity -= booking.quantity

    # Cancel all digital tickets for this booking.
    tickets = (
        db.query(Ticket)
        .filter(Ticket.booking_id == booking.id)
        .all()
    )

    for ticket in tickets:
        ticket.status = "cancelled"

    # Cancel booking.
    booking.status = "cancelled"

    # Update payment/refund record.
    payment.amount = refund_amount
    payment.status = "refunded"

    return len(tickets)


# --------------------------------------------------
# ATTENDEE CANCELS OWN BOOKING
# --------------------------------------------------

@router.post(
    "/booking/{booking_id}",
    dependencies=[Depends(verify_csrf_token)]
)
def cancel_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.user_id == current_user.id
        )
        .with_for_update()
        .first()
    )

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

    event = (
        db.query(Event)
        .filter(Event.id == booking.event_id)
        .first()
    )

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

    if (
        datetime.now(timezone.utc).replace(tzinfo=None)
        >= normalize_datetime(event.start_time)
    ):
        raise HTTPException(
            status_code=400,
            detail="Bookings cannot be cancelled after the event has started"
        )

    # Calculate refund.
    refund_amount, refund_percentage = calculate_refund(
        booking.total_amount,
        event.start_time
    )

    event_id = booking.event_id
    category_id = booking.ticket_category_id
    user_id = booking.user_id

    try:

        # Update booking, payment, tickets and inventory.
        ticket_count = cancel_booking_records(
            db,
            booking,
            refund_amount
        )

        # Save cancellation before processing other agents.
        db.commit()

    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------
    # NOTIFY WAITLIST AGENT AFTER CANCELLATION
    # --------------------------------------------------

    waitlist_result = None
    waitlist_error = None

    try:

        waitlist_result = waitlist_agent.process_waitlist(
            db,
            event_id,
            category_id
        )

    except Exception as error:

        db.rollback()
        waitlist_error = str(error)

    # --------------------------------------------------
    # NOTIFY NOTIFICATIONAGENT
    # --------------------------------------------------

    notification_result = None
    notification_error = None

    try:

        notification_result = notify_cancellation(
            db=db,
            user_id=user_id,
            booking_id=booking_id,
            event_id=event_id,
            message_text=(
                f"Your booking #{booking_id} has been cancelled. "
                f"Your refund amount is Rs. {refund_amount:.2f}."
            )
        )

    except Exception as error:

        db.rollback()
        notification_error = str(error)

    # --------------------------------------------------
    # RETURN CANCELLATION RESULT
    # --------------------------------------------------

    return {
        "message": "Booking cancelled successfully",
        "booking_id": booking_id,
        "booking_status": "cancelled",
        "refund_percentage": int(refund_percentage * 100),
        "refund_amount": refund_amount,
        "payment_status": "refunded",
        "tickets_cancelled": ticket_count,
        "waitlist_result": waitlist_result,
        "waitlist_error": waitlist_error,
        "notification_result": notification_result,
        "notification_error": notification_error,
        "refund_policy": (
            "More than 48 hours: 100%; "
            "24 to 48 hours: 50%; "
            "less than 24 hours: 0%"
        )
    }


# --------------------------------------------------
# ADMIN CANCELS EVENT AND REFUNDS BOOKINGS
# --------------------------------------------------

@router.post(
    "/event/{event_id}",
    dependencies=[Depends(verify_csrf_token)]
)
def cancel_event_and_refund(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .with_for_update()
        .first()
    )

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

    # Keep attendee IDs and booking IDs for notifications.
    notification_targets = []

    try:

        bookings = (
            db.query(Booking)
            .filter(
                Booking.event_id == event_id,
                Booking.status == "confirmed"
            )
            .with_for_update()
            .all()
        )

        total_refund = 0.0
        cancelled_bookings = 0
        cancelled_tickets = 0

        for booking in bookings:

            payment = (
                db.query(Payment)
                .filter(Payment.booking_id == booking.id)
                .first()
            )

            if not payment:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Payment record missing for booking {booking.id}"
                    )
                )

            # Admin event cancellation gives a full refund.
            refund_amount = float(booking.total_amount)

            cancelled_tickets += cancel_booking_records(
                db,
                booking,
                refund_amount
            )

            total_refund += refund_amount
            cancelled_bookings += 1

            notification_targets.append({
                "user_id": booking.user_id,
                "booking_id": booking.id,
                "event_id": event_id
            })

        # Cancel the event.
        event.status = "cancelled"

        # Cancel all waitlist entries for this event.
        waitlist_entries = (
            db.query(WaitlistEntry)
            .filter(WaitlistEntry.event_id == event_id)
            .all()
        )

        for entry in waitlist_entries:
            entry.status = "cancelled"
            entry.hold_expires_at = None

        # Save event cancellation and refunds first.
        db.commit()

    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------
    # NOTIFY ALL AFFECTED ATTENDEES
    # --------------------------------------------------

    notifications_sent = 0
    notification_errors = []

    for target in notification_targets:

        try:

            notify_cancellation(
                db=db,
                user_id=target["user_id"],
                booking_id=target["booking_id"],
                event_id=target["event_id"],
                message_text=(
                    f"Event #{event_id} has been cancelled by the "
                    f"administrator. Your booking "
                    f"#{target['booking_id']} has been cancelled. "
                    f"Your full refund is Rs. "
                    f"{float(
                        db.query(Booking)
                        .filter(Booking.id == target['booking_id'])
                        .first().total_amount
                    ):.2f}."
                )
            )

            notifications_sent += 1

        except Exception as error:

            db.rollback()

            notification_errors.append({
                "booking_id": target["booking_id"],
                "user_id": target["user_id"],
                "error": str(error)
            })

    # --------------------------------------------------
    # RETURN ADMIN CANCELLATION RESULT
    # --------------------------------------------------

    return {
        "message": "Event cancelled and full refunds processed",
        "event_id": event_id,
        "event_status": "cancelled",
        "cancelled_bookings": cancelled_bookings,
        "cancelled_tickets": cancelled_tickets,
        "total_refund": round(total_refund, 2),
        "refund_percentage": 100,
        "waitlist_entries_cancelled": len(waitlist_entries),
        "notifications_sent": notifications_sent,
        "notification_errors": notification_errors
    }
