
from getpass import getpass
from pathlib import Path
import sys

# Ensure the project root is available for imports.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.models.entities import User
from app.services.auth_service import hash_password


def main():
    print("\nEventSphere - Reset Attendee Password")

    email = input("Attendee email: ").strip().lower()

    if "@" not in email:
        print("Error: Enter a valid email address.")
        return

    password = getpass("New password (minimum 8 characters): ")
    confirm_password = getpass("Confirm new password: ")

    if len(password) < 8:
        print("Error: Password must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.email == email
        ).first()

        if not user:
            print("Error: No account found with this email.")
            return

        if user.role != "attendee":
            print("Error: This account is not an attendee account.")
            return

        if not user.is_active:
            print("Error: This attendee account is inactive.")
            return

        user.password_hash = hash_password(password)

        db.commit()

        print("\nAttendee password reset successfully!")
        print(f"Email: {user.email}")
        print("You can now log in using the new password.")

    except Exception as error:
        db.rollback()
        print(f"Error: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
