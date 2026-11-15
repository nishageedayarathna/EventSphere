
import secrets
from sqlalchemy.orm import Session

from app.models.entities import Booking, Ticket
from app.agents.message_bus import create_message


def handle_ticket_request(db: Session, message: dict):
    """Generate one unique digital ticket for each booked ticket."""

    if message.get("receiver") != "TicketAgent":
        return create_message(
            db,
            sender="TicketAgent",
            receiver=message.get("sender", "Unknown"),
            performative="REFUSE",
            content={"reason": "Message is not addressed to TicketAgent"},
            conversation_id=message.get("conversation_id")
        )

    if message.get("performative") != "REQUEST":
        return create_message(
            db,
            sender="TicketAgent",
            receiver=message.get("sender", "Unknown"),
            performative="REFUSE",
            content={"reason": "TicketAgent requires a REQUEST message"},
            conversation_id=message.get("conversation_id")
        )

    content = message.get("content", {})
    booking_id = content.get("booking_id")

    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.status == "confirmed"
    ).first()

    if not booking:
        return create_message(
            db,
            sender="TicketAgent",
            receiver=message.get("sender", "Unknown"),
            performative="REFUSE",
            content={"reason": "Confirmed booking not found"},
            conversation_id=message.get("conversation_id")
        )

    existing_tickets = db.query(Ticket).filter(
        Ticket.booking_id == booking.id
    ).count()

    if existing_tickets:
        return create_message(
            db,
            sender="TicketAgent",
            receiver=message.get("sender", "Unknown"),
            performative="REFUSE",
            content={"reason": "Tickets have already been generated for this booking"},
            conversation_id=message.get("conversation_id")
        )

    generated_tickets = []

    for _ in range(booking.quantity):
        ticket_code = "ES-" + secrets.token_urlsafe(24)

        ticket = Ticket(
            booking_id=booking.id,
            event_id=booking.event_id,
            user_id=booking.user_id,
            ticket_code=ticket_code,
            status="valid",
            checked_in=False
        )

        db.add(ticket)
        generated_tickets.append(ticket_code)

    db.commit()

    return create_message(
        db,
        sender="TicketAgent",
        receiver=message.get("sender", "BookingAPI"),
        performative="AGREE",
        content={
            "booking_id": booking.id,
            "tickets_generated": len(generated_tickets),
            "ticket_codes": generated_tickets
        },
        conversation_id=message.get("conversation_id")
    )
