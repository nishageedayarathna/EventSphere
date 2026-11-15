from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.models.entities import Notification, User, AgentState


def main():
    db = SessionLocal()

    try:
        print("\n===== NOTIFICATION REPORT =====")

        notifications = (
            db.query(Notification)
            .order_by(Notification.id.desc())
            .all()
        )

        if not notifications:
            print("No notifications found.")

        for notification in notifications:
            user = db.query(User).filter(
                User.id == notification.user_id
            ).first()

            print("\nNotification ID:", notification.id)
            print("User:", user.email if user else "Unknown")
            print("Title:", notification.title)
            print("Message:", notification.message)
            print("Read:", notification.is_read)
            print("Created:", notification.created_at)

        print("\n===== NOTIFICATION AGENT STATE =====")

        state = (
            db.query(AgentState)
            .filter(
                AgentState.agent_name == "NotificationAgent"
            )
            .first()
        )

        if state:
            print(state.state_data)
        else:
            print("NotificationAgent state not found.")

    finally:
        db.close()


if __name__ == "__main__":
    main()