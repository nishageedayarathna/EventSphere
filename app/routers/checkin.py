
import uuid

from fastapi import APIRouter, Depends, HTTPException
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


# Request model
class CheckinRequest(BaseModel):

    event_id: int = Field(gt=0)

    ticket_code: str = Field(
        min_length=5,
        max_length=150
    )


# Scan ticket endpoint
@router.post(
    "/scan",
    dependencies=[Depends(verify_csrf_token)]
)
def scan_ticket(
    data: CheckinRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_staff)
):

    # Generate unique conversation ID
    conversation_id = str(uuid.uuid4())

    # Create a structured REQUEST message
    message = {
        "sender": "CheckinAPI",
        "receiver": "CheckinAgent",
        "performative": "REQUEST",
        "content": {
            "event_id": data.event_id,
            "ticket_code": data.ticket_code.strip()
        },
        "conversation_id": conversation_id
    }

    try:

        # Send request to CheckinAgent
        response = handle_checkin_request(
            db,
            message
        )

        # Validate agent response
        if not response or "performative" not in response:
            raise HTTPException(
                status_code=500,
                detail="CheckinAgent returned an invalid response"
            )

        # Return admission decision
        return {
            "message": "Check-in request processed",
            "decision": response["performative"],
            "details": response.get("content", {}),
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Check-in processing failed: {str(error)}"
        )
