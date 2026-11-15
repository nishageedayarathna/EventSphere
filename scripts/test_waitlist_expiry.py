
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timedelta, timezone

from app.database.connection import SessionLocal
from app.models.entities import (
    WaitlistEntry,
    User,
    Event,
    TicketCategory
)


def main():
    db = SessionLocal()

    try:
        print("\n===== CREATE WAITLIST EXPIRY TEST =====")

        user = db.query(User).filter(
            User.email == "waitlisttester@gmail.com"
        ).first()

        event = db.query(Event).filter(
            Event.id == 8
        ).first()

        category = db.query(TicketCategory).filter(
            TicketCategory.id == 12,
            TicketCategory.event_id == 8
        ).first()

        if not user:
            print("Test user not found.")
            return

        if not event:
            print("Test event not found.")
            return

        if not category:
            print("Ticket category not found.")
            return

        test_entry = WaitlistEntry(
            user_id=user.id,
            event_id=event.id,
            ticket_category_id=category.id,
            status="offered",
            hold_expires_at=(
                datetime.now(timezone.utc) - timedelta(minutes=1)
            )
        )

        db.add(test_entry)
        db.commit()
        db.refresh(test_entry)

        print("\nTest offer created successfully!")
        print("Entry ID:", test_entry.id)
        print("User:", user.email)
        print("Event:", event.title)
        print("Status:", test_entry.status)
        print("Expiry:", test_entry.hold_expires_at)

        print("\nKeep your FastAPI server running.")
        print("Wait up to 30 seconds for automatic expiry.")

    except Exception as error:
        db.rollback()
        print("Error:", error)

    finally:
        db.close()


if __name__ == "__main__":
    main()
