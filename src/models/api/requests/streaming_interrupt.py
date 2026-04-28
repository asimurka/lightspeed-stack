"""Models for streaming interrupt REST API requests."""

from pydantic import BaseModel, Field, field_validator

from utils import suid


class StreamingInterruptRequest(BaseModel):
    """Model representing a request to interrupt an active streaming query.

    Attributes:
        request_id: Unique ID of the active streaming request to interrupt.
    """

    request_id: str = Field(
        description="The active streaming request ID to interrupt",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {"request_id": "123e4567-e89b-12d3-a456-426614174000"},
            ]
        },
    }

    @field_validator("request_id")
    @classmethod
    def check_request_id(cls, value: str) -> str:
        """Validate that request identifier matches expected SUID format.

        Parameters:
        ----------
            value: Request identifier submitted by the caller.

        Returns:
        -------
            str: The validated request identifier.

        Raises:
        ------
            ValueError: If the request identifier is not a valid SUID.
        """
        if not suid.check_suid(value):
            raise ValueError(f"Improper request ID {value}")
        return value
