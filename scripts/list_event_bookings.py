from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.models.entities import Booking, User, Event


def main():
    event_id = 8

    db = SessionLocal()

    try:
        event = db.query(Event).filter(
            Event.id == event_id
        ).first()

        if not event:
            print(f"Event {event_id} not found.")
            return

        print("\n--- Event Booking Details ---")
        print(f"Event ID: {event.id}")
        print(f"Event: {event.title}")

        bookings = db.query(Booking).filter(
            Booking.event_id == event_id
        ).order_by(Booking.id).all()

        if not bookings:
            print("No bookings found.")
            return

        for booking in bookings:
            user = db.query(User).filter(
                User.id == booking.user_id
            ).first()

            print("\n-----------------------------")
            print(f"Booking ID: {booking.id}")
            print(f"Attendee User ID: {booking.user_id}")
            print(f"Attendee Name: {user.full_name if user else 'Unknown'}")
            print(f"Attendee Email: {user.email if user else 'Unknown'}")
            print(f"Booking Status: {booking.status}")
            print(f"Ticket Category ID: {booking.ticket_category_id}")
            print(f"Quantity: {booking.quantity}")
            print(f"Amount: {booking.total_amount}")

    finally:
        db.close()


if __name__ == "__main__":
    main()