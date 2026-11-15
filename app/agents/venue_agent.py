
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.entities import Venue, Event
from app.agents.message_bus import create_message


TURNAROUND_MINUTES = 30


def normalize_datetime(value: datetime) -> datetime:
    """
    Make database and request datetimes comparable in UTC.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def handle_venue_request(
    db: Session,
    message: dict
):
    """
    VenueAgent receives a REQUEST message,
    checks availability and sends AGREE or REFUSE.
    """

    if message["receiver"] != "VenueAgent":
        raise ValueError("Message is not addressed to VenueAgent")

    if message["performative"] != "REQUEST":
        raise ValueError("VenueAgent expects a REQUEST message")

    content = message["content"]

    venue_id = content["venue_id"]
    start_time = datetime.fromisoformat(content["start_time"])
    end_time = datetime.fromisoformat(content["end_time"])
    total_tickets = content["total_tickets"]

    conversation_id = message["conversation_id"]

    venue = (
        db.query(Venue)
        .filter(Venue.id == venue_id)
        .first()
    )

    if not venue:
        return create_message(
            db=db,
            sender="VenueAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "The requested venue does not exist."
            },
            conversation_id=conversation_id
        )

    if total_tickets > venue.capacity:
        return create_message(
            db=db,
            sender="VenueAgent",
            receiver=message["sender"],
            performative="REFUSE",
            content={
                "reason": "Total ticket quantity exceeds venue capacity.",
                "venue_capacity": venue.capacity,
                "requested_tickets": total_tickets
            },
            conversation_id=conversation_id
        )

    requested_start = normalize_datetime(start_time)
    requested_end = normalize_datetime(end_time)

    buffer = timedelta(minutes=TURNAROUND_MINUTES)

    existing_events = (
        db.query(Event)
        .filter(
            Event.venue_id == venue_id,
            Event.status == "published"
        )
        .all()
    )

    for existing_event in existing_events:

        existing_start = normalize_datetime(
            existing_event.start_time
        )

        existing_end = normalize_datetime(
            existing_event.end_time
        )

        # Apply a 30-minute turnaround buffer
        if (
            requested_start < existing_end + buffer
            and requested_end + buffer > existing_start
        ):
            return create_message(
                db=db,
                sender="VenueAgent",
                receiver=message["sender"],
                performative="REFUSE",
                content={
                    "reason": "Venue is unavailable because another published event overlaps this time, including the turnaround buffer.",
                    "conflicting_event_id": existing_event.id,
                    "conflicting_event_title": existing_event.title
                },
                conversation_id=conversation_id
            )

    return create_message(
        db=db,
        sender="VenueAgent",
        receiver=message["sender"],
        performative="AGREE",
        content={
            "reason": "Venue is available.",
            "venue_id": venue.id,
            "venue_name": venue.name,
            "venue_capacity": venue.capacity,
            "total_tickets": total_tickets,
            "turnaround_buffer_minutes": TURNAROUND_MINUTES
        },
        conversation_id=conversation_id
    )
