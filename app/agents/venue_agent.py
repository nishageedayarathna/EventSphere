
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


from datetime import datetime, timedelta, timezone

from app.models.entities import (
    Venue,
    Event,
    VenueHireRequest
)
from app.agents.message_bus import create_message


PRIVATE_HIRE_BUFFER_MINUTES = 30
MANUAL_REVIEW_CAPACITY_PERCENTAGE = 0.80


def normalize_hire_datetime(value):
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def hire_slot_is_available(
    db,
    venue_id,
    start_time,
    end_time
):
    """Check published events and confirmed private hires."""

    buffer = timedelta(minutes=PRIVATE_HIRE_BUFFER_MINUTES)

    events = db.query(Event).filter(
        Event.venue_id == venue_id,
        Event.status == "published"
    ).all()

    for event in events:
        event_start = normalize_hire_datetime(event.start_time)
        event_end = normalize_hire_datetime(event.end_time)

        if (
            start_time < event_end + buffer
            and end_time + buffer > event_start
        ):
            return False

    hires = db.query(VenueHireRequest).filter(
        VenueHireRequest.venue_id == venue_id,
        VenueHireRequest.status.in_(["confirmed", "pending"])
    ).all()

    for hire in hires:
        hire_start = normalize_hire_datetime(hire.start_time)
        hire_end = normalize_hire_datetime(hire.end_time)

        if (
            start_time < hire_end + buffer
            and end_time + buffer > hire_start
        ):
            return False

    return True


def find_hire_alternatives(
    db,
    requested_venue,
    start_time,
    end_time,
    guest_count
):
    """Find available alternative venues and times."""

    alternatives = []

    venues = db.query(Venue).filter(
        Venue.open_for_private_hire == True,
        Venue.capacity >= guest_count,
        Venue.id != requested_venue.id
    ).all()

    # Alternative venues at the requested time
    for venue in venues:
        if hire_slot_is_available(
            db, venue.id, start_time, end_time
        ):
            alternatives.append({
                "venue_id": venue.id,
                "venue_name": venue.name,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "quoted_price": round(
                    float(venue.hourly_hire_rate)
                    * (end_time - start_time).total_seconds()
                    / 3600,
                    2
                )
            })

        if len(alternatives) >= 3:
            return alternatives

    # Alternative times at the requested venue
    for days in [1, 2, 3, 7]:
        alternative_start = start_time + timedelta(days=days)
        alternative_end = end_time + timedelta(days=days)

        if hire_slot_is_available(
            db,
            requested_venue.id,
            alternative_start,
            alternative_end
        ):
            alternatives.append({
                "venue_id": requested_venue.id,
                "venue_name": requested_venue.name,
                "start_time": alternative_start.isoformat(),
                "end_time": alternative_end.isoformat(),
                "quoted_price": round(
                    float(requested_venue.hourly_hire_rate)
                    * (alternative_end - alternative_start).total_seconds()
                    / 3600,
                    2
                )
            })

        if len(alternatives) >= 3:
            break

    return alternatives


def handle_private_hire_request(db, message):
    """VenueAgent makes decisions about private venue hire."""

    sender = message.get("sender", "Unknown")
    conversation_id = message.get("conversation_id")

    def respond(performative, content):
        return create_message(
            db,
            sender="VenueAgent",
            receiver=sender,
            performative=performative,
            content=content,
            conversation_id=conversation_id
        )

    if message.get("receiver") != "VenueAgent":
        return respond(
            "REFUSE",
            {"reason": "Message is not addressed to VenueAgent"}
        )

    if message.get("performative") != "REQUEST":
        return respond(
            "REFUSE",
            {"reason": "A REQUEST message is required"}
        )

    content = message.get("content", {})

    try:
        venue_id = int(content["venue_id"])
        guest_count = int(content["guest_count"])

        start_time = normalize_hire_datetime(
            datetime.fromisoformat(content["start_time"])
        )
        end_time = normalize_hire_datetime(
            datetime.fromisoformat(content["end_time"])
        )

    except (KeyError, TypeError, ValueError):
        return respond(
            "REFUSE",
            {"reason": "Invalid or missing hire request information"}
        )

    if end_time <= start_time:
        return respond(
            "REFUSE",
            {"reason": "End time must be after start time"}
        )

    if start_time <= datetime.now():
        return respond(
            "REFUSE",
            {"reason": "Private hire must be requested for a future time"}
        )

    if guest_count <= 0:
        return respond(
            "REFUSE",
            {"reason": "Guest count must be greater than zero"}
        )

    venue = db.query(Venue).filter(
        Venue.id == venue_id
    ).first()

    if not venue:
        return respond(
            "REFUSE",
            {"reason": "Venue not found"}
        )

    if not venue.open_for_private_hire:
        return respond(
            "REFUSE",
            {"reason": "This venue is not open for private hire"}
        )

    if guest_count > venue.capacity:
        return respond(
            "REFUSE",
            {
                "reason": "Guest count exceeds venue capacity",
                "venue_capacity": venue.capacity,
                "guest_count": guest_count
            }
        )

    duration_hours = (
        end_time - start_time
    ).total_seconds() / 3600

    quoted_price = round(
        float(venue.hourly_hire_rate) * duration_hours,
        2
    )

    if not hire_slot_is_available(
        db, venue.id, start_time, end_time
    ):
        alternatives = find_hire_alternatives(
            db,
            venue,
            start_time,
            end_time,
            guest_count
        )

        return respond(
            "PROPOSE" if alternatives else "REFUSE",
            {
                "reason": "Requested venue and time are unavailable",
                "alternatives": alternatives
            }
        )

    # Requests using more than 80% of capacity require admin review.
    if guest_count > venue.capacity * MANUAL_REVIEW_CAPACITY_PERCENTAGE:
        return respond(
            "PROPOSE",
            {
                "reason": "Large private hire request requires admin approval",
                "review_required": True,
                "venue_id": venue.id,
                "quoted_price": quoted_price,
                "guest_count": guest_count
            }
        )

    return respond(
        "AGREE",
        {
            "reason": "Venue is available and request meets automatic confirmation rules",
            "venue_id": venue.id,
            "quoted_price": quoted_price,
            "guest_count": guest_count,
            "duration_hours": duration_hours
        }
    )
