"""Server-Sent Events encoding for OpenResponses stream events."""

import json

from responses.models.events import ResponseStreamEvent


def encode_openresponses_event(event: ResponseStreamEvent) -> str:
    """Format one OpenResponses event as an SSE message.

    Args:
        event: Projected stream event.

    Returns:
        event and data lines matching the /v1/responses wire format.

    """
    payload = event.model_dump(mode="json", exclude_none=True)
    event_type = payload.get("type") or "error"
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
