"""Models for conversation REST API requests."""

from pydantic import BaseModel, Field


class ConversationUpdateRequest(BaseModel):
    """Model representing a request to update a conversation topic summary.

    Attributes:
        topic_summary: The new topic summary for the conversation.

    Example:
        ```python
        update_request = ConversationUpdateRequest(
            topic_summary="Discussion about machine learning algorithms"
        )
        ```
    """

    topic_summary: str = Field(
        ...,
        description="The new topic summary for the conversation",
        examples=["Discussion about machine learning algorithms"],
        min_length=1,
        max_length=1000,
    )

    # Reject unknown fields
    model_config = {"extra": "forbid"}
