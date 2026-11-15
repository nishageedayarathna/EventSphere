
from sqlalchemy.orm import Session

from app.models.entities import Event, TicketCategory
from app.agents.message_bus import create_message


MAX_TICKETS_PER_BOOKING = 6


def handle_booking_request(
    db: Session,
    message: dict
):
    """
    BookingAgent receives a ticket booking REQUEST
    and decides whether to accept or refuse it.
    """

    if message.get("receiver") != "BookingAgent":
        raise ValueError(
            "Message is not addressed to BookingAgent"
        )

    if message.get("performative") != "REQUEST":
        raise ValueError(
            "BookingAgent expects a REQUEST message"
        )

    content = message.get("content", {})

    event_id = content.get("event_id")
    ticket_category_id = content.get("ticket_category_id")
    quantity = content.get("quantity")

    conversation_id = message.get("conversation_id")

    if not all([
        event_id,
        ticket_category_id,
        quantity is not None
    ]):
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message.get("sender", "UnknownAgent"),
            performative="REFUSE",
            content={
                "reason": "Missing booking information."
            },
            conversation_id=conversation_id
        )

    # Rule 1: Maximum six tickets per booking
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity <= 0
        or quantity > MAX_TICKETS_PER_BOOKING
    ):
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "A booking must contain between 1 and 6 tickets.",
                "requested_quantity": quantity,
                "maximum_quantity": MAX_TICKETS_PER_BOOKING
            },
            conversation_id=conversation_id
        )

    # Rule 2: Event must exist
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if not event:
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "Event does not exist."
            },
            conversation_id=conversation_id
        )

    # Rule 3: Event must be published
    if event.status != "published":
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "Tickets can only be booked for published events.",
                "event_status": event.status
            },
            conversation_id=conversation_id
        )

    # Rule 4: Ticket category must belong to event
    category = (
        db.query(TicketCategory)
        .filter(
            TicketCategory.id == ticket_category_id,
            TicketCategory.event_id == event_id
        )
        .first()
    )

    if not category:
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "Ticket category does not belong to this event."
            },
            conversation_id=conversation_id
        )

    # Rule 5: Check ticket availability
    available_tickets = (
        category.quantity - category.sold_quantity
    )

    if quantity > available_tickets:
        return create_message(
            db=db,
            sender="BookingAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "Not enough tickets are available.",
                "available_tickets": available_tickets,
                "requested_tickets": quantity
            },
            conversation_id=conversation_id
        )

    # All decision rules passed
    total_amount = category.price * quantity

    return create_message(
        db=db,
        sender="BookingAgent",
        receiver=message["sender"],
        performative="AGREE",
        content={
            "reason": "Booking request accepted.",
            "event_id": event_id,
            "ticket_category_id": ticket_category_id,
            "quantity": quantity,
            "unit_price": category.price,
            "total_amount": total_amount,
            "available_tickets": available_tickets
        },
        conversation_id=conversation_id
    )
