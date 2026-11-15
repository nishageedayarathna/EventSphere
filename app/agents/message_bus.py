
import uuid

from sqlalchemy.orm import Session

from app.models.entities import AgentMessage


def create_message(
    db: Session,
    sender: str,
    receiver: str,
    performative: str,
    content: dict,
    conversation_id: str = None
):
    """
    Create and store a JSON agent message.
    """

    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    message = {
        "sender": sender,
        "receiver": receiver,
        "performative": performative,
        "content": content,
        "conversation_id": conversation_id
    }

    message_record = AgentMessage(
        sender=sender,
        receiver=receiver,
        performative=performative,
        content=content,
        conversation_id=conversation_id
    )

    db.add(message_record)
    db.commit()

    return message


def send_message(
    db: Session,
    message: dict
):
    """
    Store a message received from an agent.
    """

    required_fields = [
        "sender",
        "receiver",
        "performative",
        "content",
        "conversation_id"
    ]

    for field in required_fields:
        if field not in message:
            raise ValueError(
                f"Missing message field: {field}"
            )

    message_record = AgentMessage(
        sender=message["sender"],
        receiver=message["receiver"],
        performative=message["performative"],
        content=message["content"],
        conversation_id=message["conversation_id"]
    )

    db.add(message_record)
    db.commit()

    return message
