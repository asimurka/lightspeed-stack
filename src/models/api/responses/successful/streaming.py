# pylint: disable=too-many-lines

"""Models for REST API responses."""

from typing import Any

from pydantic import Field
from pydantic_core import SchemaError

from constants import MEDIA_TYPE_EVENT_STREAM
from models.api.responses.constants import (
    SUCCESSFUL_RESPONSE_DESCRIPTION,
)
from models.api.responses.successful.bases import AbstractSuccessfulResponse


class StreamingQueryResponse(AbstractSuccessfulResponse):
    """Documentation-only model for streaming query responses using Server-Sent Events (SSE)."""

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """Generate FastAPI response dict for SSE streaming with examples.

        Note: This is used for OpenAPI documentation only. The actual endpoint
        returns a StreamingResponse object, not this Pydantic model.
        """
        schema = cls.model_json_schema()
        model_examples = schema.get("examples")
        if not model_examples:
            raise SchemaError(f"Examples not found in {cls.__name__}")
        example_value = model_examples[0]
        content = {
            MEDIA_TYPE_EVENT_STREAM: {
                "schema": {"type": "string", "format": MEDIA_TYPE_EVENT_STREAM},
                "example": example_value,
            }
        }

        return {
            "description": SUCCESSFUL_RESPONSE_DESCRIPTION,
            "content": content,
            # Note: No "model" key since we're not actually serializing this model
        }

    model_config = {
        "json_schema_extra": {
            "examples": [
                (
                    'data: {"event": "start", "data": {'
                    '"conversation_id": "123e4567-e89b-12d3-a456-426614174000", '
                    '"request_id": "123e4567-e89b-12d3-a456-426614174001"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 0, "token": "No Violation"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 1, "token": ""}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 2, "token": "Hello"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 3, "token": "!"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 4, "token": " How"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 5, "token": " can"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 6, "token": " I"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 7, "token": " assist"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 8, "token": " you"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 9, "token": " today"}}\n\n'
                    'data: {"event": "token", "data": {'
                    '"id": 10, "token": "?"}}\n\n'
                    'data: {"event": "turn_complete", "data": {'
                    '"token": "Hello! How can I assist you today?"}}\n\n'
                    'data: {"event": "end", "data": {'
                    '"referenced_documents": [], '
                    '"truncated": null, "input_tokens": 11, "output_tokens": 19}, '
                    '"available_quotas": {}}\n\n'
                ),
            ]
        }
    }


class StreamingInterruptResponse(AbstractSuccessfulResponse):
    """Model representing a response to a streaming interrupt request.

    Attributes:
        request_id: The streaming request ID targeted by the interrupt call.
        interrupted: Whether an in-progress stream was interrupted.
        message: Human-readable interruption status message.

    Example:
        ```python
        response = StreamingInterruptResponse(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            interrupted=True,
            message="Streaming request interrupted",
        )
        ```
    """

    request_id: str = Field(
        description="The streaming request ID targeted by the interrupt call",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )

    interrupted: bool = Field(
        description="Whether an in-progress stream was interrupted",
        examples=[True],
    )

    message: str = Field(
        description="Human-readable interruption status message",
        examples=["Streaming request interrupted"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "123e4567-e89b-12d3-a456-426614174000",
                    "interrupted": True,
                    "message": "Streaming request interrupted",
                }
            ]
        }
    }
