
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import Venue, VenueHireRequest
from app.schemas.venue_hire import (
    VenueHireCreate,
    VenueHireDecision
)
from app.security.dependencies import require_attendee, require_admin
from app.security.csrf import verify_csrf_token
from app.agents.venue_agent import handle_private_hire_request


router = APIRouter(
    prefix="/api/venue-hire",
    tags=["Private Venue Hire"]
)


# --------------------------------------------------
# ATTENDEE: SUBMIT A PRIVATE VENUE HIRE REQUEST
# --------------------------------------------------

@router.post(
    "/requests",
    status_code=201,
    dependencies=[Depends(verify_csrf_token)]
)
def create_hire_request(
    data: VenueHireCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    conversation_id = str(uuid.uuid4())

    message = {
        "sender": "VenueHireAPI",
        "receiver": "VenueAgent",
        "performative": "REQUEST",
        "content": {
            "venue_id": data.venue_id,
            "start_time": data.start_time.isoformat(),
            "end_time": data.end_time.isoformat(),
            "purpose": data.purpose,
            "guest_count": data.guest_count
        },
        "conversation_id": conversation_id
    }

    response = handle_private_hire_request(
        db,
        message
    )

    decision = response["performative"]
    details = response["content"]

    if decision == "REFUSE":
        return {
            "message": "Private hire request refused",
            "decision": decision,
            "details": details,
            "conversation_id": conversation_id
        }

    venue = db.query(Venue).filter(
        Venue.id == data.venue_id
    ).first()

    if not venue:
        raise HTTPException(
            status_code=404,
            detail="Venue not found"
        )

    if decision == "AGREE":
        status = "confirmed"
    elif details.get("review_required"):
        status = "pending"
    else:
        status = "proposed"

    quoted_price = details.get(
        "quoted_price",
        round(
            float(venue.hourly_hire_rate)
            * (
                data.end_time - data.start_time
            ).total_seconds() / 3600,
            2
        )
    )

    hire_request = VenueHireRequest(
        user_id=current_user.id,
        venue_id=data.venue_id,
        start_time=data.start_time,
        end_time=data.end_time,
        purpose=data.purpose,
        guest_count=data.guest_count,
        quoted_price=quoted_price,
        status=status
    )

    db.add(hire_request)
    db.commit()
    db.refresh(hire_request)

    return {
        "message": "Private hire request processed",
        "request_id": hire_request.id,
        "decision": decision,
        "status": hire_request.status,
        "quoted_price": hire_request.quoted_price,
        "details": details,
        "conversation_id": conversation_id
    }


# --------------------------------------------------
# ATTENDEE: VIEW OWN HIRE REQUESTS
# --------------------------------------------------

@router.get("/my-requests")
def get_my_hire_requests(
    db: Session = Depends(get_db),
    current_user=Depends(require_attendee)
):

    requests = db.query(VenueHireRequest).filter(
        VenueHireRequest.user_id == current_user.id
    ).order_by(
        VenueHireRequest.id.desc()
    ).all()

    return {
        "total_requests": len(requests),
        "requests": [
            {
                "id": item.id,
                "venue_id": item.venue_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "purpose": item.purpose,
                "guest_count": item.guest_count,
                "quoted_price": item.quoted_price,
                "status": item.status
            }
            for item in requests
        ]
    }


# --------------------------------------------------
# ADMIN: VIEW REQUESTS NEEDING APPROVAL
# --------------------------------------------------

@router.get("/admin/pending")
def get_pending_hire_requests(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):

    requests = db.query(VenueHireRequest).filter(
        VenueHireRequest.status == "pending"
    ).order_by(
        VenueHireRequest.id.asc()
    ).all()

    return {
        "total_pending": len(requests),
        "requests": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "venue_id": item.venue_id,
                "start_time": item.start_time,
                "end_time": item.end_time,
                "purpose": item.purpose,
                "guest_count": item.guest_count,
                "quoted_price": item.quoted_price,
                "status": item.status
            }
            for item in requests
        ]
    }


# --------------------------------------------------
# ADMIN: APPROVE OR REJECT A HIRE REQUEST
# --------------------------------------------------

@router.post(
    "/admin/{request_id}/decision",
    dependencies=[Depends(verify_csrf_token)]
)
def decide_hire_request(
    request_id: int,
    data: VenueHireDecision,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin)
):

    hire = db.query(VenueHireRequest).filter(
        VenueHireRequest.id == request_id
    ).with_for_update().first()

    if not hire:
        raise HTTPException(
            status_code=404,
            detail="Venue hire request not found"
        )

    if hire.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can receive an admin decision"
        )

    if data.decision == "approved":
        hire.status = "confirmed"
    else:
        hire.status = "rejected"

    db.commit()
    db.refresh(hire)

    return {
        "message": "Admin decision saved",
        "request_id": hire.id,
        "status": hire.status,
        "admin_note": data.admin_note
    }
