
from sqlalchemy.orm import Session

from app.models.entities import AgentState, Notification
from app.agents.message_bus import create_message


class NotificationAgent:
    """
    Receives INFORM messages from other agents
    and creates notifications for users.
    """

    @staticmethod
    def handle_message(
        db: Session,
        message: dict
    ):

        # Validate message
        if not isinstance(message, dict):
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Invalid message format"
                }
            }

        # Validate receiver
        if message.get("receiver") != "NotificationAgent":
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Message is not addressed to NotificationAgent"
                }
            }

        # Validate performative
        if message.get("performative") != "INFORM":
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "NotificationAgent accepts INFORM messages only"
                }
            }

        content = message.get("content", {})

        if not isinstance(content, dict):
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Invalid message content"
                }
            }

        user_id = content.get("user_id")

        if not user_id:
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Missing user_id"
                }
            }

        title = content.get(
            "title",
            "EventSphere Notification"
        )

        notification_message = content.get("message", "")

        if (
            not isinstance(notification_message, str)
            or not notification_message.strip()
        ):
            return {
                "performative": "REFUSE",
                "content": {
                    "reason": "Notification message cannot be empty"
                }
            }

        try:

            # Create user notification
            notification = Notification(
                user_id=user_id,
                title=title,
                message=notification_message.strip()
            )

            db.add(notification)
            db.flush()

            # Get or create persistent agent state
            state = (
                db.query(AgentState)
                .filter(
                    AgentState.agent_name == "NotificationAgent"
                )
                .first()
            )

            if state is None:

                state = AgentState(
                    agent_name="NotificationAgent",
                    state_data={
                        "notifications_created": 0
                    }
                )

                db.add(state)
                db.flush()

            # Update persistent state
            state_data = dict(state.state_data or {})

            state_data["notifications_created"] = (
                state_data.get("notifications_created", 0) + 1
            )

            state.state_data = state_data

            # Save notification and state
            db.flush()

            # Send response to original sender
            response = create_message(
                db=db,
                sender="NotificationAgent",
                receiver=message.get("sender", "UnknownAgent"),
                performative="AGREE",
                content={
                    "notification_id": notification.id,
                    "user_id": user_id,
                    "status": "Notification created",
                    "notifications_created": state_data[
                        "notifications_created"
                    ]
                },
                conversation_id=message.get("conversation_id")
            )

            return response

        except Exception:
            db.rollback()
            raise


notification_agent = NotificationAgent()
