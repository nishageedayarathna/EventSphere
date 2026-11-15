
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone

from app.database.connection import SessionLocal
from app.models.entities import WaitlistEntry, User, Event


def make_aware(value):

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def main():

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        print("\n===== COMPLETE WAITLIST REPORT =====")
        print("Current UTC:", now)

        entries = (
            db.query(WaitlistEntry)
            .order_by(WaitlistEntry.id.asc())
            .all()
        )

        if not entries:
            print("\nNo waitlist entries found.")
            return

        for entry in entries:

            user = (
                db.query(User)
                .filter(User.id == entry.user_id)
                .first()
            )

            event = (
                db.query(Event)
                .filter(Event.id == entry.event_id)
                .first()
            )

            expiry = make_aware(entry.hold_expires_at)

            if entry.status == "offered":

                if expiry and expiry > now:
                    hold_state = "ACTIVE"
                else:
                    hold_state = "EXPIRED OR INVALID"

            elif entry.status == "waiting":
                hold_state = "WAITING FOR OFFER"

            else:
                hold_state = entry.status.upper()

            print("\n--------------------------------")
            print("ENTRY ID:", entry.id)
            print("USER ID:", entry.user_id)
            print("NAME:", user.full_name if user else "Unknown")
            print("EMAIL:", user.email if user else "Unknown")
            print("EVENT:", event.title if event else "Unknown")
            print("STATUS:", entry.status)
            print("EXPIRY:", entry.hold_expires_at)
            print("HOLD STATE:", hold_state)

        print("\n===== REPORT COMPLETED =====")

    except Exception as error:
        print("Error:", error)

    finally:
        db.close()


if __name__ == "__main__":
    main()
