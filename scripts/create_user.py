from getpass import getpass

from app.database.connection import SessionLocal, create_database
from app.models.entities import User
from app.services.auth_service import hash_password


def main():

    create_database()

    print("\nEventSphere - Create Privileged User")

    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    role = input("Role (admin/staff): ").strip().lower()

    if role not in ["admin", "staff"]:
        print("Error: Role must be admin or staff.")
        return

    if len(full_name) < 2:
        print("Error: Enter a valid full name.")
        return

    if "@" not in email:
        print("Error: Enter a valid email address.")
        return

    password = getpass("Password (minimum 8 characters): ")
    confirm_password = getpass("Confirm password: ")

    if len(password) < 8:
        print("Error: Password must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    db = SessionLocal()

    try:
        existing_user = db.query(User).filter(
            User.email == email
        ).first()

        if existing_user:
            print("Error: This email is already registered.")
            return

        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True
        )

        db.add(new_user)
        db.commit()

        print(f"\nSuccessfully created {role} account.")
        print(f"Email: {email}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()