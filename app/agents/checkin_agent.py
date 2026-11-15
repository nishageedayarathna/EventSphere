
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.models.entities import Ticket, Event
from app.agents.message_bus import create_message


class CheckinAgent:

    name = "CheckinAgent"

    def normalize_datetime(self, value):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        return value

    def send_response(
        self,
        db,
        receiver,
        performative,
        content,
        conversation_id
    ):
        return create_message(
            db,
            sender=self.name,
            receiver=receiver,
            performative=performative,
            content=content,
            conversation_id=conversation_id
        )

    def handle_message(self, db: Session, message: dict):

        sender = message.get("sender", "Unknown")
        conversation_id = message.get("conversation_id")

        # Validate receiver
        if message.get("receiver") != self.name:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Message is not addressed to CheckinAgent"},
                conversation_id
            )

        # Validate message type
        if message.get("performative") != "REQUEST":
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "A REQUEST message is required"},
                conversation_id
            )

        content = message.get("content", {})

        ticket_code = content.get("ticket_code")
        event_id = content.get("event_id")

        if not ticket_code or not event_id:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket code and event ID are required"},
                conversation_id
            )

        # Find ticket
        ticket = db.query(Ticket).filter(
            Ticket.ticket_code == ticket_code
        ).first()

        if not ticket:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Invalid ticket code"},
                conversation_id
            )

        # Check event ownership
        if ticket.event_id != event_id:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket belongs to another event"},
                conversation_id
            )

        # Check ticket status
        if ticket.status == "cancelled":
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket has been cancelled"},
                conversation_id
            )

        if ticket.status != "valid":
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket is not valid"},
                conversation_id
            )

        # Check previous admission
        if ticket.checked_in:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket has already been used"},
                conversation_id
            )

        # Find event
        event = db.query(Event).filter(
            Event.id == ticket.event_id
        ).first()

        if not event:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Event not found"},
                conversation_id
            )

        if event.status == "cancelled":
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Event has been cancelled"},
                conversation_id
            )

        # Check event time
        now = datetime.now()

        event_start = self.normalize_datetime(event.start_time)
        event_end = self.normalize_datetime(event.end_time)

        if now < event_start:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Check-in is not open yet"},
                conversation_id
            )

        if now > event_end:
            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Event check-in time has ended"},
                conversation_id
            )

        # Atomic update: prevents duplicate admission
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket.id,
                Ticket.checked_in == False,
                Ticket.status == "valid"
            )
            .values(
                checked_in=True,
                checked_in_at=now
            )
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.rollback()

            return self.send_response(
                db,
                sender,
                "REFUSE",
                {"reason": "Ticket has already been checked in"},
                conversation_id
            )

        db.commit()

        return self.send_response(
            db,
            sender,
            "AGREE",
            {
                "message": "Ticket accepted. Attendee may enter.",
                "ticket_id": ticket.id,
                "event_id": ticket.event_id,
                "checked_in": True,
                "checked_in_at": now.isoformat()
            },
            conversation_id
        )


checkin_agent = CheckinAgent()


def handle_checkin_request(db: Session, message: dict):
    return checkin_agent.handle_message(db, message)
