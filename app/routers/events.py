
from datetime import timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import (
    Event,
    Venue,
    TicketCategory,
    User
)
from app.schemas.event import (
    EventCreate,
    EventUpdate,
    EventResponse
)
from app.security.dependencies import require_admin
from app.security.csrf import verify_csrf_token
from app.agents.venue_agent import handle_venue_request


router = APIRouter(
    prefix="/api/events",
    tags=["Event Management"]
)


def to_iso(value):
    """Convert a datetime into an ISO-formatted string."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.isoformat()


def check_venue_approval(
    db: Session,
    venue_id: int,
    start_time,
    end_time,
    total_tickets: int
):
    """
    Send a REQUEST message to VenueAgent.
    Continue only when VenueAgent responds AGREE.
    """

    message = {
        "sender": "EventManagement",
        "receiver": "VenueAgent",
        "performative": "REQUEST",
        "content": {
            "venue_id": venue_id,
            "start_time": to_iso(start_time),
            "end_time": to_iso(end_time),
            "total_tickets": total_tickets
        },
        "conversation_id": str(uuid.uuid4())
    }

    response = handle_venue_request(db, message)

    if response["performative"] != "AGREE":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "VenueAgent refused the event request.",
                "reason": response["content"]
            }
        )


# --------------------------------------------------
# 1. VIEW ALL EVENTS
# Public access
# --------------------------------------------------

@router.get("/")
def get_all_events(
    db: Session = Depends(get_db)
):
    events = (
        db.query(Event)
        .order_by(Event.id.desc())
        .all()
    )

    return events


# --------------------------------------------------
# 2. VIEW ONE EVENT
# Public access
# --------------------------------------------------

@router.get("/{event_id}")
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    categories = (
        db.query(TicketCategory)
        .filter(TicketCategory.event_id == event_id)
        .all()
    )

    return {
        "event": event,
        "ticket_categories": categories
    }


# --------------------------------------------------
# 3. CREATE EVENT
# Admin only
# --------------------------------------------------

@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(verify_csrf_token)]
)
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    venue = (
        db.query(Venue)
        .filter(Venue.id == data.venue_id)
        .first()
    )

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Selected venue does not exist"
        )

    total_tickets = sum(
        category.quantity
        for category in data.ticket_categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Total ticket quantity ({total_tickets}) "
                f"exceeds venue capacity ({venue.capacity})."
            )
        )

    # If the admin wants to publish immediately,
    # ask VenueAgent for approval first.
    if data.status == "published":
        check_venue_approval(
            db,
            data.venue_id,
            data.start_time,
            data.end_time,
            total_tickets
        )

    new_event = Event(
        title=data.title,
        category=data.category,
        venue_id=data.venue_id,
        start_time=data.start_time,
        end_time=data.end_time,
        description=data.description,
        status=data.status,
        created_by=current_user.id
    )

    try:
        db.add(new_event)
        db.flush()

        for category in data.ticket_categories:
            new_category = TicketCategory(
                event_id=new_event.id,
                name=category.name,
                price=category.price,
                quantity=category.quantity,
                sold_quantity=0
            )

            db.add(new_category)

        db.commit()
        db.refresh(new_event)

        return {
            "message": "Event created successfully",
            "event": new_event,
            "total_tickets": total_tickets
        }

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 4. UPDATE EVENT
# Admin only
# Only draft events can be edited
# --------------------------------------------------

@router.put(
    "/{event_id}",
    dependencies=[Depends(verify_csrf_token)]
)
def update_event(
    event_id: int,
    data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft events can be edited."
        )

    update_data = data.model_dump(exclude_unset=True)

    new_venue_id = update_data.get(
        "venue_id",
        event.venue_id
    )

    new_start_time = update_data.get(
        "start_time",
        event.start_time
    )

    new_end_time = update_data.get(
        "end_time",
        event.end_time
    )

    if new_end_time <= new_start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time."
        )

    venue = (
        db.query(Venue)
        .filter(Venue.id == new_venue_id)
        .first()
    )

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Selected venue does not exist."
        )

    existing_categories = (
        db.query(TicketCategory)
        .filter(TicketCategory.event_id == event_id)
        .all()
    )

    total_tickets = sum(
        category.quantity
        for category in existing_categories
    )

    if total_tickets > venue.capacity:
        raise HTTPException(
            status_code=400,
            detail="Ticket quantity exceeds the new venue capacity."
        )

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    return {
        "message": "Draft event updated successfully",
        "event": event
    }


# --------------------------------------------------
# 5. PUBLISH EVENT
# Admin only
# VenueAgent must approve
# --------------------------------------------------

@router.post(
    "/{event_id}/publish",
    dependencies=[Depends(verify_csrf_token)]
)
def publish_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    if event.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft events can be published."
        )

    categories = (
        db.query(TicketCategory)
        .filter(TicketCategory.event_id == event_id)
        .all()
    )

    if not categories:
        raise HTTPException(
            status_code=400,
            detail="Add at least one ticket category before publishing."
        )

    total_tickets = sum(
        category.quantity
        for category in categories
    )

    # Ask VenueAgent to check availability.
    check_venue_approval(
        db,
        event.venue_id,
        event.start_time,
        event.end_time,
        total_tickets
    )

    event.status = "published"

    db.commit()
    db.refresh(event)

    return {
        "message": "Event published successfully",
        "event": event
    }


# --------------------------------------------------
# 6. CANCEL EVENT
# Admin only
# --------------------------------------------------

@router.post(
    "/{event_id}/cancel",
    dependencies=[Depends(verify_csrf_token)]
)
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    event = (
        db.query(Event)
        .filter(Event.id == event_id)
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
            detail="Event is already cancelled."
        )

    event.status = "cancelled"

    db.commit()
    db.refresh(event)

    return {
        "message": "Event cancelled successfully",
        "event_id": event.id,
        "status": event.status
    }
