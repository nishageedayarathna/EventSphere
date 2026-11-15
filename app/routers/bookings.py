
import base64
import secrets
import uuid

from io import BytesIO

import qrcode

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.database.connection import get_db

from app.models.entities import (
    Booking,
    Payment,
    Ticket,
    TicketCategory
)

from app.schemas.booking import BookingCreate

from app.security.dependencies import require_attendee
from app.security.csrf import verify_csrf_token

from app.agents.booking_agent import handle_booking_request
from app.agents.ticket_agent import handle_ticket_request

from app.agents.message_bus import (
    create_message,
    deliver_message
)


router = APIRouter(
    prefix="/api/bookings",
    tags=["Ticket Booking"]
)


MAX_TICKETS_PER_BOOKING = 6


# --------------------------------------------------
# CREATE BOOKING
# --------------------------------------------------

@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(verify_csrf_token)]
)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    conversation_id = str(uuid.uuid4())

    try:

        # ------------------------------------------
        # 1. SEND REQUEST TO BOOKINGAGENT
        # ------------------------------------------

        booking_message = create_message(
            db=db,
            sender="BookingAPI",
            receiver="BookingAgent",
            performative="REQUEST",
            content={
                "event_id": data.event_id,
                "ticket_category_id": data.ticket_category_id,
                "quantity": data.quantity
            },
            conversation_id=conversation_id
        )

        booking_response = handle_booking_request(
            db,
            booking_message
        )

        if booking_response["performative"] != "AGREE":

            db.commit()

            raise HTTPException(
                status_code=409,
                detail={
                    "message": "BookingAgent refused the request",
                    "reason": booking_response["content"]
                }
            )

        # ------------------------------------------
        # 2. VALIDATE TICKET CATEGORY
        # ------------------------------------------

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
                detail="Ticket category not found"
            )

        total_amount = category.price * data.quantity

        # ------------------------------------------
        # 3. ATOMIC TICKET ALLOCATION
        # ------------------------------------------

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
            .execution_options(
                synchronize_session=False
            )
        )

        if allocation.rowcount != 1:

            db.rollback()

            refusal = create_message(
                db=db,
                sender="BookingAgent",
                receiver="BookingAPI",
                performative="REFUSE",
                content={
                    "reason": (
                        "Tickets were sold before allocation "
                        "could be completed."
                    ),
                    "requested_quantity": data.quantity
                },
                conversation_id=conversation_id
            )

            db.commit()

            raise HTTPException(
                status_code=409,
                detail="Sorry, these tickets are no longer available."
            )

        # ------------------------------------------
        # 4. CREATE BOOKING
        # ------------------------------------------

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

        # ------------------------------------------
        # 5. SIMULATED PAYMENT
        # ------------------------------------------

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
        db.flush()

        db.commit()
        db.refresh(new_booking)

        # ------------------------------------------
        # 6. SEND REQUEST TO TICKETAGENT
        # ------------------------------------------

        ticket_message = create_message(
            db=db,
            sender="BookingAPI",
            receiver="TicketAgent",
            performative="REQUEST",
            content={
                "booking_id": new_booking.id
            },
            conversation_id=conversation_id
        )

        ticket_response = handle_ticket_request(
            db,
            ticket_message
        )

        if ticket_response["performative"] != "AGREE":

            db.commit()

            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "Booking was confirmed, "
                        "but ticket generation failed."
                    ),
                    "reason": ticket_response["content"],
                    "booking_id": new_booking.id
                }
            )

        db.commit()

        # ------------------------------------------
        # 7. INFORM NOTIFICATIONAGENT
        # ------------------------------------------

        notification_message = create_message(
            db=db,
            sender="BookingAgent",
            receiver="NotificationAgent",
            performative="INFORM",
            content={
                "user_id": current_user.id,
                "title": "Booking Successful",
                "message": (
                    f"Your booking #{new_booking.id} "
                    "was successful. Your ticket is ready."
                ),
                "booking_id": new_booking.id,
                "event_id": new_booking.event_id
            },
            conversation_id=conversation_id
        )

        notification_response = deliver_message(
            db=db,
            message=notification_message
        )

        if notification_response.get("performative") != "AGREE":

            db.commit()

            raise HTTPException(
                status_code=500,
                detail={
                    "message": (
                        "Booking and ticket generation succeeded, "
                        "but notification creation failed."
                    ),
                    "reason": notification_response
                }
            )

        db.commit()
        db.refresh(new_booking)

        # ------------------------------------------
        # 8. RETURN RESULT
        # ------------------------------------------

        return {
            "message": "Booking successful!",

            "booking": {
                "id": new_booking.id,
                "user_id": new_booking.user_id,
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

            "booking_agent": {
                "decision": booking_response["performative"],
                "details": booking_response["content"]
            },

            "ticket_agent": {
                "decision": ticket_response["performative"],
                "details": ticket_response["content"]
            },

            "notification_agent": {
                "decision": notification_response["performative"],
                "details": notification_response["content"]
            },

            "conversation_id": conversation_id
        }

    except HTTPException:
        raise

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Booking failed: {str(error)}"
        )


# --------------------------------------------------
# VIEW ATTENDEE BOOKINGS
# --------------------------------------------------

@router.get("/my-bookings")
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id
        )
        .order_by(
            Booking.id.desc()
        )
        .all()
    )

    result = []

    for booking in bookings:

        result.append({
            "booking_id": booking.id,
            "event_id": booking.event_id,
            "ticket_category_id": booking.ticket_category_id,
            "quantity": booking.quantity,
            "total_amount": booking.total_amount,
            "status": booking.status,
            "created_at": booking.created_at
        })

    return {
        "total_bookings": len(result),
        "bookings": result
    }


# --------------------------------------------------
# VIEW ATTENDEE DIGITAL TICKETS WITH QR CODES
# --------------------------------------------------

@router.get("/my-tickets")
def get_my_tickets(
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.user_id == current_user.id
        )
        .order_by(
            Ticket.id.desc()
        )
        .all()
    )

    result = []

    for ticket in tickets:

        # Generate QR code from unique ticket code
        qr_image = qrcode.make(
            ticket.ticket_code
        )

        buffer = BytesIO()

        qr_image.save(
            buffer,
            format="PNG"
        )

        qr_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        result.append({
            "ticket_id": ticket.id,
            "booking_id": ticket.booking_id,
            "event_id": ticket.event_id,
            "ticket_code": ticket.ticket_code,
            "status": ticket.status,
            "checked_in": ticket.checked_in,
            "qr_code": (
                "data:image/png;base64," + qr_base64
            )
        })

    return {
        "total_tickets": len(result),
        "tickets": result
    }
