
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.models.entities import (
    Event,
    Venue,
    Booking,
    Payment,
    Ticket,
    AgentMessage,
    AgentState,
)
from app.security.dependencies import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Dashboard"]
)


@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):
    # Total confirmed tickets sold
    tickets_sold = (
        db.query(func.coalesce(func.sum(Booking.quantity), 0))
        .filter(Booking.status == "confirmed")
        .scalar()
    )

    # Simulated successful payment revenue
    revenue = (
        db.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .filter(Payment.status == "simulated_success")
        .scalar()
    )

    # Total successful check-ins
    check_ins = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.checked_in.is_(True))
        .scalar()
    )

    total_events = db.query(func.count(Event.id)).scalar()
    total_venues = db.query(func.count(Venue.id)).scalar()

    # Capacity and ticket sales for each event
    events = db.query(Event).order_by(Event.id.desc()).all()

    capacity_lines = []

    for event in events:
        venue = (
            db.query(Venue)
            .filter(Venue.id == event.venue_id)
            .first()
        )

        sold = (
            db.query(func.coalesce(func.sum(Booking.quantity), 0))
            .filter(
                Booking.event_id == event.id,
                Booking.status == "confirmed"
            )
            .scalar()
        )

        capacity = venue.capacity if venue else 0
        sold = int(sold or 0)

        capacity_lines.append(
            f"{event.title}: {sold} tickets sold / "
            f"{capacity} venue capacity"
        )

    return {
        "tickets_sold": int(tickets_sold or 0),
        "simulated_revenue": round(float(revenue or 0), 2),
        "check_ins": int(check_ins or 0),
        "total_events": int(total_events or 0),
        "total_venues": int(total_venues or 0),
        "capacity_per_event": (
            "\n".join(capacity_lines)
            if capacity_lines
            else "No events available."
        )
    }


@router.get("/agent-messages")
def get_agent_messages(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):
    messages = (
        db.query(AgentMessage)
        .order_by(AgentMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "messages": [
            {
                "id": message.id,
                "sender": message.sender,
                "receiver": message.receiver,
                "performative": message.performative,
                "content": message.content,
                "conversation_id": message.conversation_id,
                "created_at": message.created_at
            }
            for message in messages
        ]
    }


@router.get("/agent-states")
def get_agent_states(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):
    states = (
        db.query(AgentState)
        .order_by(AgentState.agent_name.asc())
        .all()
    )

    return {
        "states": [
            {
                "agent_name": state.agent_name,
                "state_data": state.state_data,
                "updated_at": state.updated_at
            }
            for state in states
        ]
    }
