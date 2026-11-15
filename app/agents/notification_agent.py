from sqlalchemy.orm import Session

from app.models.entities import AgentState, Notification
from app.agents.message_bus import create_message


class NotificationAgent:
    """
    Receives INFORM messages from other agents
    and creates notifications for users.
    """

    @staticmethod
    def handle_message(db: Session, message: dict):
        if message.get("receiver") != "NotificationAgent":
            return {
                "status": "REFUSE",
                "reason": "Message is not addressed to NotificationAgent"
            }

        if message.get("performative") != "INFORM":
            return {
                "status": "REFUSE",
                "reason": "NotificationAgent accepts INFORM messages only"
            }

        content = message.get("content", {})
        user_id = content.get("user_id")

        if not user_id:
            return {
                "status": "REFUSE",
                "reason": "Missing user_id in notification message"
            }

        title = content.get("title", "EventSphere Notification")
        notification_message = content.get("message", "")

        if not notification_message:
            return {
                "status": "REFUSE",
                "reason": "Notification message cannot be empty"
            }

        notification = Notification(
            user_id=user_id,
            title=title,
            message=notification_message
        )

        db.add(notification)

        # Update persistent agent state.
        state = (
            db.query(AgentState)
            .filter(AgentState.agent_name == "NotificationAgent")
            .first()
        )

        if not state:
            state = AgentState(
                agent_name="NotificationAgent",
                state_data={"notifications_created": 0}
            )
            db.add(state)

        state_data = dict(state.state_data or {})
        state_data["notifications_created"] = (
            state_data.get("notifications_created", 0) + 1
        )
        state.state_data = state_data

        db.commit()
        db.refresh(notification)

        return create_message(
            db=db,
            sender="NotificationAgent",
            receiver=message.get("sender", "UnknownAgent"),
            performative="AGREE",
            content={
                "notification_id": notification.id,
                "user_id": user_id,
                "status": "Notification created"
            },
            conversation_id=message.get("conversation_id")
        )


notification_agent = NotificationAgent()