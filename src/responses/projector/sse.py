"""Encode OpenResponses events as Server-Sent Events."""

import json

from responses.models.events import ResponseStreamEvent


def encode_openresponses_event(event: ResponseStreamEvent) -> str:
    """Format one OpenResponses event as an SSE chunk.

    Args:
        event: Projected OpenResponses stream event.

    Returns:
        SSE string with event type and JSON data, matching ``/v1/responses``.

    """
    payload = event.model_dump(mode="json", exclude_none=True)
    event_type = payload.get("type") or "error"
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
