
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.entities import (
    AgentState,
    Event,
    TicketCategory,
    WaitlistEntry
)

from app.agents.message_bus import create_message, deliver_message


OFFER_HOLD_MINUTES = 10


def get_utc_now():
    return datetime.now(timezone.utc)


def make_datetime_aware(value):
    """
    SQLite may return datetime values without timezone information.
    Treat those values as UTC.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


class WaitlistAgent:
    """
    Manages ticket waiting lists.

    Rules:
    1. FIFO ticket offers.
    2. Each offer is held for 10 minutes.
    3. Expired offers are released.
    4. Released tickets are offered to the next attendee.
    5. Persistent agent state is maintained.
    """

    # --------------------------------------------------
    # PERSISTENT AGENT STATE
    # --------------------------------------------------

    def save_state(self, db: Session, key: str, value):

        state = (
            db.query(AgentState)
            .filter(
                AgentState.agent_name == "WaitlistAgent"
            )
            .first()
        )

        if state is None:
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

        return state_data

    def update_state(self, db: Session, values: dict):
        """
        Update multiple persistent state values together.
        """

        state = (
            db.query(AgentState)
            .filter(
                AgentState.agent_name == "WaitlistAgent"
            )
            .first()
        )

        if state is None:
            state = AgentState(
                agent_name="WaitlistAgent",
                state_data={}
            )
            db.add(state)
            db.flush()

        state_data = dict(state.state_data or {})
        state_data.update(values)

        state.state_data = state_data

        db.commit()

        return state_data

    # --------------------------------------------------
    # RECEIVE AGENT MESSAGE
    # --------------------------------------------------

    def handle_message(self, db: Session, message: dict):
        """
        Handle structured messages addressed to WaitlistAgent.
        """

        if not isinstance(message, dict):
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Invalid message format"
                }
            }

        if message.get("receiver") != "WaitlistAgent":
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Message is not addressed to WaitlistAgent"
                }
            }

        if message.get("performative") != "REQUEST":
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "WaitlistAgent accepts REQUEST messages only"
                }
            }

        content = message.get("content", {})

        if not isinstance(content, dict):
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Invalid message content"
                }
            }

        event_id = content.get("event_id")
        category_id = content.get("ticket_category_id")

        if not event_id or not category_id:
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Missing event_id or ticket_category_id"
                }
            }

        try:
            result = self.process_waitlist(
                db,
                int(event_id),
                int(category_id)
            )

            if result.get("status") == "REFUSE":
                performative = "REFUSE"
            else:
                performative = "AGREE"

            return create_message(
                db=db,
                sender="WaitlistAgent",
                receiver=message.get("sender", "UnknownAgent"),
                performative=performative,
                content=result,
                conversation_id=message.get("conversation_id")
            )

        except Exception:
            db.rollback()
            raise

    # --------------------------------------------------
    # NOTIFY USER THROUGH NOTIFICATIONAGENT
    # --------------------------------------------------

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

        response = deliver_message(
            db=db,
            message=message
        )

        if response.get("performative") != "AGREE":
            raise Exception(
                f"NotificationAgent rejected the message: {response}"
            )

        db.commit()

        return response

    # --------------------------------------------------
    # PROCESS WAITLIST
    # --------------------------------------------------

    def process_waitlist(
        self,
        db: Session,
        event_id: int,
        ticket_category_id: int
    ):
        """
        Offer available tickets to waiting customers in FIFO order.
        """

        event = (
            db.query(Event)
            .filter(Event.id == event_id)
            .first()
        )

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

        # --------------------------------------------------
        # EXPIRE OLD OFFERS
        # --------------------------------------------------

        expired_entries = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.event_id == event_id,
                WaitlistEntry.ticket_category_id == ticket_category_id,
                WaitlistEntry.status == "offered"
            )
            .all()
        )

        expired_count = 0

        for entry in expired_entries:

            expiry = make_datetime_aware(
                entry.hold_expires_at
            )

            if expiry and expiry <= now:

                entry.status = "expired"
                entry.hold_expires_at = None

                db.flush()

                self.notify_user(
                    db,
                    entry.user_id,
                    "Waitlist offer expired",
                    "Your 10-minute ticket offer has expired."
                )

                expired_count += 1

        db.commit()

        # --------------------------------------------------
        # COUNT ACTIVE OFFERS
        # --------------------------------------------------

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

            expiry = make_datetime_aware(
                entry.hold_expires_at
            )

            if expiry and expiry > now:
                active_hold_count += 1

        # --------------------------------------------------
        # CHECK AVAILABLE TICKETS
        # --------------------------------------------------

        available_tickets = (
            category.quantity
            - category.sold_quantity
            - active_hold_count
        )

        if available_tickets <= 0:

            self.update_state(
                db,
                {
                    "last_processed_event_id": event_id,
                    "last_ticket_category_id": ticket_category_id,
                    "last_offered_count": 0,
                    "last_expired_count": expired_count,
                    "last_action": "WAITLIST_PROCESSED_NO_TICKETS",
                    "last_processed_at": now.isoformat()
                }
            )

            return {
                "status": "INFORM",
                "event_id": event_id,
                "ticket_category_id": ticket_category_id,
                "offered_count": 0,
                "expired_count": expired_count,
                "message": "No tickets are currently available to offer"
            }

        # --------------------------------------------------
        # SELECT WAITING ENTRIES USING FIFO
        # --------------------------------------------------

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

        # --------------------------------------------------
        # MAKE TICKET OFFERS
        # --------------------------------------------------

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
                    f"You have {OFFER_HOLD_MINUTES} minutes "
                    "to accept it."
                )
            )

            offered_count += 1

        # --------------------------------------------------
        # UPDATE PERSISTENT STATE
        # --------------------------------------------------

        self.update_state(
            db,
            {
                "last_processed_event_id": event_id,
                "last_ticket_category_id": ticket_category_id,
                "last_offered_count": offered_count,
                "last_expired_count": expired_count,
                "last_action": "WAITLIST_PROCESSED",
                "last_processed_at": now.isoformat()
            }
        )

        return {
            "status": "AGREE",
            "event_id": event_id,
            "ticket_category_id": ticket_category_id,
            "offered_count": offered_count,
            "expired_count": expired_count,
            "message": "Waitlist processing completed"
        }

    # --------------------------------------------------
    # SCHEDULED OFFER EXPIRY
    # --------------------------------------------------

    def expire_offers(self, db: Session):
        """
        Scheduled task:
        expire old offers and offer released tickets
        to the next waiting customers.
        """

        now = get_utc_now()

        offered_entries = (
            db.query(WaitlistEntry)
            .filter(
                WaitlistEntry.status == "offered"
            )
            .all()
        )

        affected_categories = set()
        expired_count = 0

        for entry in offered_entries:

            expiry = make_datetime_aware(
                entry.hold_expires_at
            )

            if expiry and expiry <= now:

                entry.status = "expired"
                entry.hold_expires_at = None

                affected_categories.add(
                    (
                        entry.event_id,
                        entry.ticket_category_id
                    )
                )

                db.commit()

                self.notify_user(
                    db,
                    entry.user_id,
                    "Waitlist offer expired",
                    (
                        "Your ticket offer expired because "
                        "it was not accepted within 10 minutes."
                    )
                )

                expired_count += 1

        db.commit()

        # --------------------------------------------------
        # OFFER RELEASED TICKETS TO NEXT ATTENDEES
        # --------------------------------------------------

        new_offers = 0

        for event_id, category_id in affected_categories:

            result = self.process_waitlist(
                db,
                event_id,
                category_id
            )

            if result.get("status") == "AGREE":
                new_offers += result.get("offered_count", 0)

        # --------------------------------------------------
        # UPDATE SCHEDULED TASK STATE
        # --------------------------------------------------

        self.update_state(
            db,
            {
                "last_expiry_check": now.isoformat(),
                "last_expired_count": expired_count,
                "last_new_offers": new_offers,
                "last_action": "EXPIRY_CHECK_COMPLETED"
            }
        )

        return {
            "expired_count": expired_count,
            "new_offers": new_offers
        }


waitlist_agent = WaitlistAgent()
