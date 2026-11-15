
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.security.dependencies import require_staff
from app.security.csrf import verify_csrf_token

from app.agents.checkin_agent import handle_checkin_request


router = APIRouter(
    prefix="/api/checkin",
    tags=["Staff Check-in"]
)


class CheckinRequest(BaseModel):

    event_id: int = Field(gt=0)

    ticket_code: str = Field(
        min_length=5,
        max_length=150
    )


@router.post(
    "/scan",
    dependencies=[Depends(verify_csrf_token)]
)
def scan_ticket(
    data: CheckinRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_staff)
):

    conversation_id = str(uuid.uuid4())

    # Create a REQUEST message for CheckinAgent
    message = {
        "sender": "CheckinAPI",
        "receiver": "CheckinAgent",
        "performative": "REQUEST",
        "content": {
            "event_id": data.event_id,
            "ticket_code": data.ticket_code
        },
        "conversation_id": conversation_id
    }

    # Send message to CheckinAgent
    response = handle_checkin_request(
        db,
        message
    )

    return {
        "message": "Check-in request processed",
        "decision": response["performative"],
        "details": response["content"],
        "conversation_id": conversation_id
    }
