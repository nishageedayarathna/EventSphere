from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.entities import (
    AgentState,
    Event,
    TicketCategory,
    WaitlistEntry
)
from app.agents.message_bus import create_message
from app.agents.notification_agent import notification_agent


OFFER_HOLD_MINUTES = 10


def get_utc_now():
    return datetime.now(timezone.utc)


def make_datetime_aware(value):
    """
    SQLite may return a datetime without timezone information.
    Treat such values as UTC for comparisons.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


class WaitlistAgent:
    """
    Manages the ticket waiting list.

    Rules:
    1. Offers available tickets to waiting customers in FIFO order.
    2. Holds each offered ticket for 10 minutes.
    3. Expires offers that are not accepted in time.
    4. Offers expired or released tickets to the next customer.
    """

    def save_state(self, db: Session, key: str, value):
        state = (
            db.query(AgentState)
            .filter(AgentState.agent_name == "WaitlistAgent")
            .first()
        )

        if not state:
            state = AgentState(
                agent_name="WaitlistAgent",
                state_data={}
            )
            db.add(state)
            db.flush()

        state_data = dict(state.state_data or {})
        state_data[key] = value
        state.state_data = state_data
        db.commit()

    def notify_user(
        self,
        db: Session,
        user_id: int,
        title: str,
        message_text: str
    ):
        message = create_message(
            db=db,
            sender="WaitlistAgent",
            receiver="NotificationAgent",
            performative="INFORM",
            content={
                "user_id": user_id,
                "title": title,
                "message": message_text
            }
        )

        return notification_agent.handle_message(db, message)

    def process_waitlist(
        self,
        db: Session,
        event_id: int,
        ticket_category_id: int
    ):
        """
        Offer currently available tickets to waiting customers.
        Each waiting-list entry represents one ticket.
        """

        event = db.query(Event).filter(Event.id == event_id).first()

        category = (
            db.query(TicketCategory)
            .filter(
                TicketCategory.id == ticket_category_id,
                TicketCategory.event_id == event_id
            )
            .first()
        )

        if not event or event.status != "published":
            return {
                "status": "REFUSE",
                "reason": "Event is not available"
            }

        if not category:
            return {
                "status": "REFUSE",
                "reason": "Ticket category not found"
            }

        now = get_utc_now()

        # Expire old offers before checking available tickets.
        expired_entries = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.event_id == event_id,
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "offered"
            )
            .all()
        )

        for entry in expired_entries:
            expiry = make_datetime_aware(entry.hold_expires_at)

            if expiry and expiry <= now:
                entry.status = "expired"
                entry.hold_expires_at = None

                self.notify_user(
                    db,
                    entry.user_id,
                    "Waitlist offer expired",
                    "Your 10-minute ticket offer has expired."
                )

        db.commit()

        # Count offers that are still being held.
        active_offers = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.event_id == event_id,
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "offered"
            )
            .all()
        )

        active_hold_count = 0

        for entry in active_offers:
            expiry = make_datetime_aware(entry.hold_expires_at)

            if expiry and expiry > now:
                active_hold_count += 1

        available_tickets = (
            category.quantity
            - category.sold_quantity
            - active_hold_count
        )

        if available_tickets <= 0:
            return {
                "status": "INFORM",
                "message": "No tickets are currently available to offer"
            }

        # FIFO: the lowest entry ID is the oldest waiting request.
        waiting_entries = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.event_id == event_id,
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "waiting"
            )
            .order_by(WaitlistEntry.id.asc())
            .limit(available_tickets)
            .all()
        )

        offered_count = 0

        for entry in waiting_entries:
            entry.status = "offered"
            entry.hold_expires_at = (
                now + timedelta(minutes=OFFER_HOLD_MINUTES)
            )

            db.commit()

            self.notify_user(
                db,
                entry.user_id,
                "A ticket is available!",
                (
                    f"A ticket for {event.title} is available. "
                    f"You have {OFFER_HOLD_MINUTES} minutes to accept it."
                )
            )

            offered_count += 1

        self.save_state(
            db,
            "last_processed_event_id",
            event_id
        )

        self.save_state(
            db,
            "last_offered_count",
            offered_count
        )

        return {
            "status": "AGREE",
            "offered_count": offered_count,
            "message": "Waitlist processing completed"
        }

    def expire_offers(self, db: Session):
        """
        Scheduled task:
        expire old offers and offer released tickets
        to the next waiting customers.
        """

        now = get_utc_now()

        offered_entries = (
            db.query(WaitlistEntry)
            .filter(WaitlistEntry.status == "offered")
            .all()
        )

        affected_categories = set()
        expired_count = 0

        for entry in offered_entries:
            expiry = make_datetime_aware(entry.hold_expires_at)

            if expiry and expiry <= now:
                entry.status = "expired"
                entry.hold_expires_at = None

                affected_categories.add(
                    (entry.event_id, entry.ticket_category_id)
                )

                self.notify_user(
                    db,
                    entry.user_id,
                    "Waitlist offer expired",
                    "Your ticket offer expired because it was not accepted within 10 minutes."
                )

                expired_count += 1

        db.commit()

        # Process each affected event/category again.
        new_offers = 0

        for event_id, category_id in affected_categories:
            result = self.process_waitlist(
                db,
                event_id,
                category_id
            )

            if result.get("status") == "AGREE":
                new_offers += result.get("offered_count", 0)

        self.save_state(
            db,
            "last_expiry_check",
            now.isoformat()
        )

        self.save_state(
            db,
            "last_expired_count",
            expired_count
        )

        return {
            "expired_count": expired_count,
            "new_offers": new_offers
        }


waitlist_agent = WaitlistAgent()