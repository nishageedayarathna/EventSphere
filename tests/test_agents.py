from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models.entities import (
    AgentMessage,
    AgentState,
    Booking,
    Event,
    Notification,
    Ticket,
    TicketCategory,
    User,
    Venue,
    WaitlistEntry,
)
from app.agents.venue_agent import handle_venue_request
from app.agents.booking_agent import handle_booking_request
from app.agents.ticket_agent import handle_ticket_request
from app.agents.waitlist_agent import WaitlistAgent
from app.agents.notification_agent import notification_agent
from app.agents.checkin_agent import checkin_agent


@pytest.fixture()
def db():
    """Use a fresh isolated SQLite database for every test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False
    )
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def sample(db):
    user = User(
        full_name="Test Attendee",
        email="attendee@example.test",
        password_hash="not-a-real-password-hash",
        role="attendee",
    )
    admin = User(
        full_name="Test Admin",
        email="admin@example.test",
        password_hash="not-a-real-password-hash",
        role="admin",
    )
    db.add_all([user, admin])
    db.flush()

    venue = Venue(
        name="Main Hall",
        location="Campus",
        capacity=100,
        description="Test venue",
        image="",
        hourly_hire_rate=1000,
        open_for_private_hire=True,
    )
    db.add(venue)
    db.flush()

    start = datetime.now(timezone.utc) + timedelta(days=3)
    event = Event(
        title="Test Concert",
        category="Concert",
        venue_id=venue.id,
        start_time=start,
        end_time=start + timedelta(hours=2),
        description="Test event",
        status="published",
        created_by=admin.id,
    )
    db.add(event)
    db.flush()

    category = TicketCategory(
        event_id=event.id,
        name="Standard",
        price=500,
        quantity=10,
        sold_quantity=0,
    )
    db.add(category)
    db.commit()

    return {
        "user": user,
        "admin": admin,
        "venue": venue,
        "event": event,
        "category": category,
    }


def message(receiver, content, sender="TestClient", performative="REQUEST"):
    return {
        "sender": sender,
        "receiver": receiver,
        "performative": performative,
        "content": content,
        "conversation_id": "pytest-conversation-001",
    }


# --------------------------------------------------
# VENUE AGENT TESTS
# --------------------------------------------------

def test_venue_agent_refuses_ticket_quantity_above_capacity(db, sample):
    sample["venue"].capacity = 5
    db.commit()

    response = handle_venue_request(
        db,
        message(
            "VenueAgent",
            {
                "venue_id": sample["venue"].id,
                "start_time": (
                    datetime.now(timezone.utc) + timedelta(days=4)
                ).isoformat(),
                "end_time": (
                    datetime.now(timezone.utc) + timedelta(days=4, hours=2)
                ).isoformat(),
                "total_tickets": 6,
            },
        ),
    )

    assert response["performative"] == "REFUSE"
    assert "capacity" in response["content"]["reason"].lower()


def test_venue_agent_refuses_overlapping_published_event(db, sample):
    existing = sample["event"]
    requested_start = existing.start_time + timedelta(minutes=10)
    requested_end = requested_start + timedelta(hours=1)

    response = handle_venue_request(
        db,
        message(
            "VenueAgent",
            {
                "venue_id": sample["venue"].id,
                "start_time": requested_start.isoformat(),
                "end_time": requested_end.isoformat(),
                "total_tickets": 20,
            },
        ),
    )

    assert response["performative"] == "REFUSE"
    assert "overlap" in response["content"]["reason"].lower()


# --------------------------------------------------
# BOOKING AGENT TESTS
# --------------------------------------------------

def test_booking_agent_refuses_more_than_six_tickets(db, sample):
    response = handle_booking_request(
        db,
        message(
            "BookingAgent",
            {
                "event_id": sample["event"].id,
                "ticket_category_id": sample["category"].id,
                "quantity": 7,
            },
        ),
    )

    assert response["performative"] == "REFUSE"
    assert "between 1 and 6" in response["content"]["reason"]


def test_booking_agent_refuses_quantity_above_remaining_inventory(db, sample):
    sample["category"].sold_quantity = 8
    db.commit()

    response = handle_booking_request(
        db,
        message(
            "BookingAgent",
            {
                "event_id": sample["event"].id,
                "ticket_category_id": sample["category"].id,
                "quantity": 3,
            },
        ),
    )

    assert response["performative"] == "REFUSE"
    assert response["content"]["available_tickets"] == 2


# --------------------------------------------------
# TICKET AGENT TESTS
# --------------------------------------------------

def test_ticket_agent_generates_one_unique_code_per_ticket(db, sample):
    booking = Booking(
        user_id=sample["user"].id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        quantity=3,
        total_amount=1500,
        status="confirmed",
    )
    db.add(booking)
    db.commit()

    response = handle_ticket_request(
        db,
        message("TicketAgent", {"booking_id": booking.id}),
    )

    tickets = db.query(Ticket).filter(
        Ticket.booking_id == booking.id
    ).all()

    codes = [ticket.ticket_code for ticket in tickets]

    assert response["performative"] == "AGREE"
    assert len(tickets) == 3
    assert len(set(codes)) == 3
    assert all(code.startswith("ES-") for code in codes)


def test_ticket_agent_refuses_duplicate_ticket_generation(db, sample):
    booking = Booking(
        user_id=sample["user"].id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        quantity=1,
        total_amount=500,
        status="confirmed",
    )
    db.add(booking)
    db.flush()

    db.add(
        Ticket(
            booking_id=booking.id,
            event_id=sample["event"].id,
            user_id=sample["user"].id,
            ticket_code="ES-existing-code",
            status="valid",
            checked_in=False,
        )
    )
    db.commit()

    response = handle_ticket_request(
        db,
        message("TicketAgent", {"booking_id": booking.id}),
    )

    assert response["performative"] == "REFUSE"
    assert "already" in response["content"]["reason"].lower()


# --------------------------------------------------
# WAITLIST AGENT TESTS
# --------------------------------------------------

def test_waitlist_agent_offers_to_oldest_waiting_entry_first(db, sample):
    first = WaitlistEntry(
        user_id=sample["user"].id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        status="waiting",
    )

    second_user = User(
        full_name="Second Attendee",
        email="second@example.test",
        password_hash="not-a-real-password-hash",
        role="attendee",
    )
    db.add(second_user)
    db.flush()

    second = WaitlistEntry(
        user_id=second_user.id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        status="waiting",
    )

    db.add_all([first, second])
    db.commit()

    result = WaitlistAgent().process_waitlist(
        db,
        sample["event"].id,
        sample["category"].id,
    )

    db.refresh(first)
    db.refresh(second)

    assert result["status"] == "AGREE"
    assert first.status == "offered"
    assert second.status == "offered"
    assert first.hold_expires_at is not None
    assert second.hold_expires_at is not None
    assert db.query(Notification).count() == 2


def test_waitlist_agent_expires_old_offer_and_reoffers_to_waiting_user(
    db, sample
):
    old_user = sample["user"]

    next_user = User(
        full_name="Next Attendee",
        email="next@example.test",
        password_hash="not-a-real-password-hash",
        role="attendee",
    )
    db.add(next_user)
    db.flush()

    expired_entry = WaitlistEntry(
        user_id=old_user.id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        status="offered",
        hold_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    waiting_entry = WaitlistEntry(
        user_id=next_user.id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        status="waiting",
    )

    db.add_all([expired_entry, waiting_entry])
    db.commit()

    result = WaitlistAgent().expire_offers(db)

    db.refresh(expired_entry)
    db.refresh(waiting_entry)

    assert result["expired_count"] == 1
    assert expired_entry.status == "expired"
    assert waiting_entry.status == "offered"


# --------------------------------------------------
# NOTIFICATION AGENT TEST
# --------------------------------------------------

def test_notification_agent_creates_notification_and_persists_state(
    db, sample
):
    response = notification_agent.handle_message(
        db,
        message(
            "NotificationAgent",
            {
                "user_id": sample["user"].id,
                "title": "Booking update",
                "message": "Your booking has been confirmed.",
            },
            sender="BookingAgent",
            performative="INFORM",
        ),
    )

    notification = db.query(Notification).one()

    state = db.query(AgentState).filter_by(
        agent_name="NotificationAgent"
    ).one()

    assert response["performative"] == "AGREE"
    assert notification.user_id == sample["user"].id
    assert notification.title == "Booking update"
    assert state.state_data["notifications_created"] == 1


# --------------------------------------------------
# CHECK-IN AGENT TESTS
# --------------------------------------------------

def test_checkin_agent_admits_valid_ticket_once(db, sample):
    # Use local naive datetime because CheckinAgent currently
    # compares event times with datetime.now().
    now = datetime.now()

    sample["event"].start_time = now - timedelta(hours=1)
    sample["event"].end_time = now + timedelta(hours=1)

    booking = Booking(
        user_id=sample["user"].id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        quantity=1,
        total_amount=500,
        status="confirmed",
    )
    db.add(booking)
    db.flush()

    ticket = Ticket(
        booking_id=booking.id,
        event_id=sample["event"].id,
        user_id=sample["user"].id,
        ticket_code="ES-checkin-once",
        status="valid",
        checked_in=False,
    )
    db.add(ticket)
    db.commit()

    request = message(
        "CheckinAgent",
        {
            "ticket_code": ticket.ticket_code,
            "event_id": sample["event"].id,
        },
        sender="StaffAPI",
    )

    first_response = checkin_agent.handle_message(db, request)
    second_response = checkin_agent.handle_message(db, request)

    assert first_response["performative"] == "AGREE", first_response
    assert second_response["performative"] == "REFUSE"
    assert "already" in second_response["content"]["reason"].lower()


def test_checkin_agent_rejects_ticket_for_wrong_event(db, sample):
    # Use the same local naive datetime convention.
    now = datetime.now()

    sample["event"].start_time = now - timedelta(hours=1)
    sample["event"].end_time = now + timedelta(hours=1)

    booking = Booking(
        user_id=sample["user"].id,
        event_id=sample["event"].id,
        ticket_category_id=sample["category"].id,
        quantity=1,
        total_amount=500,
        status="confirmed",
    )
    db.add(booking)
    db.flush()

    ticket = Ticket(
        booking_id=booking.id,
        event_id=sample["event"].id,
        user_id=sample["user"].id,
        ticket_code="ES-wrong-event",
        status="valid",
        checked_in=False,
    )
    db.add(ticket)
    db.commit()

    response = checkin_agent.handle_message(
        db,
        message(
            "CheckinAgent",
            {
                "ticket_code": ticket.ticket_code,
                "event_id": sample["event"].id + 999,
            },
            sender="StaffAPI",
        ),
    )

    assert response["performative"] == "REFUSE"
    assert "another event" in response["content"]["reason"].lower()


# --------------------------------------------------
# OVERBOOKING TEST
# --------------------------------------------------

def test_atomic_ticket_allocation_prevents_overbooking(db, sample):
    """Test conditional SQL allocation used by the booking API."""

    category = sample["category"]
    category.quantity = 5
    category.sold_quantity = 4
    db.commit()

    first_allocation = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == category.id,
            TicketCategory.sold_quantity + 1 <= TicketCategory.quantity,
        )
        .values(
            sold_quantity=TicketCategory.sold_quantity + 1
        )
    )
    db.commit()

    second_allocation = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == category.id,
            TicketCategory.sold_quantity + 1 <= TicketCategory.quantity,
        )
        .values(
            sold_quantity=TicketCategory.sold_quantity + 1
        )
    )
    db.commit()

    db.refresh(category)

    assert first_allocation.rowcount == 1
    assert second_allocation.rowcount == 0
    assert category.sold_quantity == category.quantity


# --------------------------------------------------
# AGENT MESSAGE LOG TEST
# --------------------------------------------------

def test_venue_agent_message_is_logged_with_conversation_id(db, sample):
    response = handle_venue_request(
        db,
        message(
            "VenueAgent",
            {
                "venue_id": sample["venue"].id,
                "start_time": (
                    datetime.now(timezone.utc) + timedelta(days=10)
                ).isoformat(),
                "end_time": (
                    datetime.now(timezone.utc)
                    + timedelta(days=10, hours=2)
                ).isoformat(),
                "total_tickets": 50,
            },
        ),
    )

    log = db.query(AgentMessage).filter_by(
        conversation_id="pytest-conversation-001"
    ).one()

    assert response["performative"] == "AGREE"
    assert log.sender == "VenueAgent"
    assert log.receiver == "TestClient"
    assert log.performative == "AGREE"