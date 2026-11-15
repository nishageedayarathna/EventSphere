
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.models.entities import TicketCategory
from app.agents.waitlist_agent import waitlist_agent


def main():
    event_id = 8
    category_id = 12

    db = SessionLocal()

    try:
        category = db.query(TicketCategory).filter(
            TicketCategory.id == category_id,
            TicketCategory.event_id == event_id
        ).first()

        if not category:
            print("Ticket category not found.")
            return

        print("\n--- Before Processing ---")
        print(f"Total tickets: {category.quantity}")
        print(f"Sold tickets: {category.sold_quantity}")
        print(
            f"Available tickets: "
            f"{category.quantity - category.sold_quantity}"
        )

        print("\nProcessing WaitlistAgent...")

        result = waitlist_agent.process_waitlist(
            db,
            event_id,
            category_id
        )

        print("\n--- WaitlistAgent Result ---")
        print(result)

    except Exception as error:
        db.rollback()
        print("Error:", error)

    finally:
        db.close()


if __name__ == "__main__":
    main()
