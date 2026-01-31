from pydantic import BaseModel


class SlackInteractionPayload(BaseModel):
    """
    Parsed Slack interaction payload.

    Slack sends this when a user clicks a button in a message.
    """
    type: str  # "block_actions" for button clicks
    user: dict  # {"id": "U123", "username": "john", "name": "John Doe"}
    channel: dict  # {"id": "C123", "name": "incidents"}
    message: dict  # The message containing the button
    actions: list  # List of actions taken
    response_url: str  # URL to send follow-up messages
    trigger_id: str  # For opening modals
