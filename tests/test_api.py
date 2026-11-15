from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.connection import Base, get_db
from app.models.entities import (
    User, Venue, Event, TicketCategory, Booking, Payment,
    Ticket, WaitlistEntry, VenueHireRequest, AgentMessage
)
from app.services.auth_service import hash_password


PASSWORD = "TestPassword123!"


@pytest.fixture
def system():
    """Isolated SQLite database and authenticated test clients."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    users = {}

    for role, email in [
        ("admin", "admin@gmail.com"),
        ("staff", "staff@gmail.com"),
        ("attendee", "attendee@gmail.com"),
        ("attendee", "attendee2@gmail.com"),
    ]:
        user = User(
            full_name=f"Test {role.title()}",
            email=email,
            password_hash=hash_password(PASSWORD),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        users[email] = user.id

    db.commit()
    db.close()

    def client_for(email):
        client = TestClient(app)
        csrf = client.get("/api/auth/csrf")
        assert csrf.status_code == 200

        token = csrf.json()["csrf_token"]

        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": PASSWORD},
            headers={"X-CSRF-Token": token},
        )

        assert login.status_code == 200, login.text
        return client, login.json()["csrf_token"]

    clients = {
        "admin": client_for("admin@gmail.com"),
        "staff": client_for("staff@gmail.com"),
        "attendee": client_for("attendee@gmail.com"),
        "attendee2": client_for("attendee2@gmail.com"),
        "anonymous": (TestClient(app), None),
    }

    def db_session():
        return TestingSessionLocal()

    yield {
        "clients": clients,
        "users": users,
        "db": db_session,
    }

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def post(client_and_token, url, payload=None):
    client, token = client_and_token

    return client.post(
        url,
        json=payload,
        headers={"X-CSRF-Token": token} if token else {},
    )


def make_venue(system, admin_client=None, name="Test Hall", capacity=100):
    admin_client = admin_client or system["clients"]["admin"]

    response = post(admin_client, "/api/venues/", {
        "name": name,
        "location": "University Campus",
        "capacity": capacity,
        "description": "Automated test venue",
        "image": "",
        "hourly_hire_rate": 1000,
        "open_for_private_hire": True,
    })

    assert response.status_code == 201, response.text
    return response.json()


def make_event(system, status="published", quantity=10, start=None, venue=None):
    admin = system["clients"]["admin"]
    venue = venue or make_venue(system)

    start = start or (
        datetime.now(timezone.utc) + timedelta(days=5)
    )
    end = start + timedelta(hours=2)

    response = post(admin, "/api/events/", {
        "title": "Automated Test Event",
        "category": "Music",
        "venue_id": venue["id"],
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "description": "Created by API integration tests",
        "status": status,
        "ticket_categories": [
            {
                "name": "Standard",
                "price": 500,
                "quantity": quantity,
            }
        ],
    })

    assert response.status_code == 201, response.text

    body = response.json()

    return (
        body["event"],
        body["event"]["id"],
        body["total_tickets"],
    )


def book_ticket(
    system,
    event_id,
    category_id,
    quantity=1,
    attendee="attendee",
):
    return post(
        system["clients"][attendee],
        "/api/bookings/",
        {
            "event_id": event_id,
            "ticket_category_id": category_id,
            "quantity": quantity,
        },
    )


# --------------------------------------------------
# APPLICATION AND AUTHENTICATION
# --------------------------------------------------

def test_health_and_database_endpoints(system):
    client = system["clients"]["anonymous"][0]

    health = client.get("/api/health")
    database = client.get("/api/database")

    assert health.status_code == 200
    assert health.json()["status"] == "running"

    assert database.status_code == 200
    assert "users" in database.json()["tables"]
    assert "events" in database.json()["tables"]


def test_frontend_pages_are_served(system):
    client = system["clients"]["anonymous"][0]

    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_registration_creates_attendee_and_rejects_duplicate(system):
    client = system["clients"]["anonymous"][0]

    csrf = client.get("/api/auth/csrf").json()["csrf_token"]

    payload = {
        "full_name": "New Test User",
        "email": "newuser@gmail.com",
        "password": "StrongPass123!",
    }

    headers = {"X-CSRF-Token": csrf}

    first = client.post(
        "/api/auth/register",
        json=payload,
        headers=headers,
    )

    second = client.post(
        "/api/auth/register",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert first.json()["user"]["role"] == "attendee"
    assert second.status_code == 409


def test_login_rejects_wrong_password(system):
    client = system["clients"]["anonymous"][0]

    csrf = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/auth/login",
        json={
            "email": "attendee@gmail.com",
            "password": "wrong-password",
        },
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 401


def test_csrf_protection_blocks_mutating_request_without_token(system):
    client = system["clients"]["anonymous"][0]

    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "No CSRF",
            "email": "nocsrf@gmail.com",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 403


def test_current_user_and_logout(system):
    client, token = system["clients"]["attendee"]

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["role"] == "attendee"

    logout = post(
        (client, token),
        "/api/auth/logout",
    )

    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# --------------------------------------------------
# ROLE-BASED ACCESS CONTROL
# --------------------------------------------------

def test_role_access_checks_and_forbidden_routes(system):
    admin, _ = system["clients"]["admin"]
    staff, _ = system["clients"]["staff"]
    attendee, _ = system["clients"]["attendee"]
    anonymous, _ = system["clients"]["anonymous"]

    assert admin.get("/api/admin/access-check").status_code == 200
    assert staff.get("/api/staff/access-check").status_code == 200
    assert attendee.get("/api/attendee/access-check").status_code == 200

    assert attendee.get("/api/admin/access-check").status_code == 403
    assert attendee.get("/api/staff/access-check").status_code == 403

    assert anonymous.get("/api/attendee/access-check").status_code == 401


# --------------------------------------------------
# VENUE API
# --------------------------------------------------

def test_venue_create_list_get_and_update(system):
    venue = make_venue(system)

    admin, _ = system["clients"]["admin"]

    assert admin.get("/api/venues/").status_code == 200

    fetched = admin.get(f"/api/venues/{venue['id']}")

    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test Hall"

    updated = admin.put(
        f"/api/venues/{venue['id']}",
        json={"name": "Updated Hall"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Hall"

    forbidden = post(
        system["clients"]["attendee"],
        "/api/venues/",
        {
            "name": "Forbidden Venue",
            "location": "Campus",
            "capacity": 50,
            "hourly_hire_rate": 100,
        },
    )

    assert forbidden.status_code == 403


def test_get_missing_venue_returns_404(system):
    client, _ = system["clients"]["anonymous"]

    assert client.get("/api/venues/99999").status_code == 404


# --------------------------------------------------
# EVENT API
# --------------------------------------------------

def test_event_create_publish_and_public_browse(system):
    venue = make_venue(system)

    event, event_id, _ = make_event(
        system,
        status="draft",
        venue=venue,
    )

    admin, token = system["clients"]["admin"]

    assert admin.get("/api/events/").status_code == 200

    details = admin.get(f"/api/events/{event_id}")

    assert details.status_code == 200
    assert len(details.json()["ticket_categories"]) == 1

    published = post(
        (admin, token),
        f"/api/events/{event_id}/publish",
    )

    assert published.status_code == 200, published.text
    assert published.json()["event"]["status"] == "published"


def test_event_creation_rejects_ticket_total_above_venue_capacity(system):
    venue = make_venue(system, capacity=5)

    admin = system["clients"]["admin"]

    start = datetime.now(timezone.utc) + timedelta(days=8)

    response = post(admin, "/api/events/", {
        "title": "Too Many Tickets",
        "category": "Music",
        "venue_id": venue["id"],
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=2)).isoformat(),
        "description": "Capacity test",
        "status": "draft",
        "ticket_categories": [
            {
                "name": "Standard",
                "price": 100,
                "quantity": 6,
            }
        ],
    })

    assert response.status_code == 400


def test_published_event_cannot_be_edited(system):
    _, event_id, _ = make_event(system, status="published")

    admin, token = system["clients"]["admin"]

    response = admin.put(
        f"/api/events/{event_id}",
        json={"title": "Changed Published Event"},
        headers={"X-CSRF-Token": token},
    )

    assert response.status_code == 400


def test_event_cancel_endpoint_changes_status(system):
    _, event_id, _ = make_event(system, status="draft")

    admin, token = system["clients"]["admin"]

    response = post(
        (admin, token),
        f"/api/events/{event_id}/cancel",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


# --------------------------------------------------
# BOOKING AND DIGITAL TICKET API
# --------------------------------------------------

def test_booking_creates_payment_and_digital_tickets(system):
    _, event_id, _ = make_event(system, quantity=5)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    response = book_ticket(
        system,
        event_id,
        category_id,
        quantity=2,
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["booking"]["quantity"] == 2
    assert body["payment"]["status"] == "simulated_success"
    assert body["booking_agent"]["decision"] == "AGREE"
    assert body["ticket_agent"]["decision"] == "AGREE"

    client, _ = system["clients"]["attendee"]

    bookings = client.get("/api/bookings/my-bookings")
    tickets = client.get("/api/bookings/my-tickets")

    assert bookings.status_code == 200
    assert bookings.json()["total_bookings"] == 1

    assert tickets.status_code == 200
    assert tickets.json()["total_tickets"] == 2

    assert all(
        ticket["qr_code"].startswith("data:image/png;base64,")
        for ticket in tickets.json()["tickets"]
    )


def test_booking_rejects_more_than_six_tickets(system):
    _, event_id, _ = make_event(system, quantity=10)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    response = book_ticket(
        system,
        event_id,
        category_id,
        quantity=7,
    )

    assert response.status_code == 422


def test_booking_rejects_sold_out_inventory(system):
    _, event_id, _ = make_event(system, quantity=1)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    first = book_ticket(system, event_id, category_id, quantity=1)
    second = book_ticket(system, event_id, category_id, quantity=1)

    assert first.status_code == 201
    assert second.status_code == 409


# --------------------------------------------------
# CHECK-IN API
# --------------------------------------------------

def test_staff_checkin_accepts_once_and_rejects_duplicate(system):
    # CheckinAgent currently compares event times with datetime.now()
    # so this test uses local time instead of UTC time.
    start = datetime.now() - timedelta(hours=1)

    _, event_id, _ = make_event(
        system,
        quantity=2,
        start=start,
    )

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    booking = book_ticket(
        system,
        event_id,
        category_id,
    )

    assert booking.status_code == 201, booking.text

    ticket_code = (
        booking.json()["ticket_agent"]["details"]["ticket_codes"][0]
    )

    staff = system["clients"]["staff"]

    payload = {
        "event_id": event_id,
        "ticket_code": ticket_code,
    }

    first = post(
        staff,
        "/api/checkin/scan",
        payload,
    )

    second = post(
        staff,
        "/api/checkin/scan",
        payload,
    )

    assert first.status_code == 200
    assert first.json()["decision"] == "AGREE", first.json()

    assert second.status_code == 200
    assert second.json()["decision"] == "REFUSE", second.json()


def test_attendee_cannot_use_staff_checkin_api(system):
    attendee = system["clients"]["attendee"]

    response = post(
        attendee,
        "/api/checkin/scan",
        {
            "event_id": 1,
            "ticket_code": "ES-not-a-real-ticket",
        },
    )

    assert response.status_code == 403


# --------------------------------------------------
# CANCELLATION AND REFUNDS
# --------------------------------------------------

def test_attendee_cancellation_refunds_full_amount_when_more_than_48h(
    system,
):
    _, event_id, _ = make_event(system, quantity=3)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    booking = book_ticket(
        system,
        event_id,
        category_id,
        quantity=1,
    )

    booking_id = booking.json()["booking"]["id"]

    response = post(
        system["clients"]["attendee"],
        f"/api/cancellations/booking/{booking_id}",
    )

    assert response.status_code == 200, response.text
    assert response.json()["refund_percentage"] == 100
    assert response.json()["refund_amount"] == 500
    assert response.json()["booking_status"] == "cancelled"


def test_admin_event_cancellation_processes_full_refunds(system):
    _, event_id, _ = make_event(system, quantity=3)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    booking = book_ticket(
        system,
        event_id,
        category_id,
        quantity=2,
    )

    assert booking.status_code == 201

    response = post(
        system["clients"]["admin"],
        f"/api/cancellations/event/{event_id}",
    )

    assert response.status_code == 200, response.text
    assert response.json()["refund_percentage"] == 100
    assert response.json()["cancelled_bookings"] == 1
    assert response.json()["cancelled_tickets"] == 2


# --------------------------------------------------
# PRIVATE VENUE HIRE
# --------------------------------------------------

def test_private_hire_auto_confirms_and_calculates_price(system):
    venue = make_venue(system)

    start = datetime.now(timezone.utc) + timedelta(days=20)

    response = post(
        system["clients"]["attendee"],
        "/api/venue-hire/requests",
        {
            "venue_id": venue["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "purpose": "Birthday celebration",
            "guest_count": 30,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "AGREE"
    assert response.json()["status"] == "confirmed"
    assert response.json()["quoted_price"] == 2000


def test_large_private_hire_requires_admin_review(system):
    venue = make_venue(system, capacity=100)

    start = datetime.now(timezone.utc) + timedelta(days=25)

    response = post(
        system["clients"]["attendee"],
        "/api/venue-hire/requests",
        {
            "venue_id": venue["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
            "purpose": "Large university gathering",
            "guest_count": 90,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "PROPOSE"
    assert response.json()["status"] == "pending"

    admin = system["clients"]["admin"]

    pending = admin[0].get("/api/venue-hire/admin/pending")

    assert pending.status_code == 200

    request_id = response.json()["request_id"]

    decision = post(
        admin,
        f"/api/venue-hire/admin/{request_id}/decision",
        {
            "decision": "approved",
            "admin_note": "Approved by automated test",
        },
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"


def test_attendee_can_view_own_hire_requests(system):
    venue = make_venue(system)

    start = datetime.now(timezone.utc) + timedelta(days=30)

    post(
        system["clients"]["attendee"],
        "/api/venue-hire/requests",
        {
            "venue_id": venue["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
            "purpose": "Small family event",
            "guest_count": 10,
        },
    )

    response = system["clients"]["attendee"][0].get(
        "/api/venue-hire/my-requests"
    )

    assert response.status_code == 200
    assert response.json()["total_requests"] == 1


# --------------------------------------------------
# WAITLIST API
# --------------------------------------------------

def test_waitlist_join_and_duplicate_join_rejected(system):
    _, event_id, _ = make_event(system, quantity=1)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    sold = book_ticket(
        system,
        event_id,
        category_id,
    )

    assert sold.status_code == 201

    client, token = system["clients"]["attendee2"]

    url = (
        f"/api/waitlist/join?"
        f"event_id={event_id}&ticket_category_id={category_id}"
    )

    first = client.post(
        url,
        headers={"X-CSRF-Token": token},
    )

    second = client.post(
        url,
        headers={"X-CSRF-Token": token},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "waiting"
    assert second.status_code == 400

    entries = client.get("/api/waitlist/my-entries")

    assert entries.status_code == 200
    assert len(entries.json()) == 1


# --------------------------------------------------
# AGENT MESSAGE PERSISTENCE
# --------------------------------------------------

def test_agent_messages_are_persisted_during_booking(system):
    _, event_id, _ = make_event(system, quantity=2)

    db = system["db"]()

    category_id = (
        db.query(TicketCategory)
        .filter_by(event_id=event_id)
        .first()
        .id
    )

    db.close()

    response = book_ticket(
        system,
        event_id,
        category_id,
    )

    assert response.status_code == 201

    db = system["db"]()

    messages = db.query(AgentMessage).all()

    db.close()

    assert any(
        message.sender == "BookingAgent"
        for message in messages
    )

    assert any(
        message.sender == "TicketAgent"
        for message in messages
    )

    assert all(
        message.conversation_id
        for message in messages
    )