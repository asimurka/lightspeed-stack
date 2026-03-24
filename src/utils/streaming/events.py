"""Streaming events for Responses API."""

import json
from constants import (
    MEDIA_TYPE_JSON,
    MEDIA_TYPE_TEXT,
    LLM_TOKEN_EVENT,
    LLM_TOOL_CALL_EVENT,
    LLM_TOOL_RESULT_EVENT,
    LLM_TURN_COMPLETE_EVENT,
)
from log import get_logger
from models.responses import AbstractErrorResponse

logger = get_logger(__name__)


def format_stream_data(d: dict) -> str:
    r"""Serialize a dict as one SSE `data:` frame.

    Parameters:
        d: Payload to JSON-encode.

    Returns:
        SSE-formatted string (``data: ...\n\n``).
    """
    data = json.dumps(d)
    return f"data: {data}\n\n"


def stream_event(data: dict, event_type: str, media_type: str) -> str:
    """Build a single SSE event string for the given media type.

    Args:
        data: Event payload.
        event_type: Logical event name (token, tool call, etc.).
        media_type: Client media type (JSON vs plain text).

    Returns:
        SSE-formatted string for this event.
    """
    if media_type == MEDIA_TYPE_TEXT:
        if event_type == LLM_TOKEN_EVENT:
            return data.get("token", "")
        if event_type == LLM_TOOL_CALL_EVENT:
            return f"[Tool Call: {data.get('function_name', 'unknown')}]\n"
        if event_type == LLM_TOOL_RESULT_EVENT:
            return "[Tool Result]\n"
        if event_type == LLM_TURN_COMPLETE_EVENT:
            return ""
        return ""

    return format_stream_data(
        {
            "event": event_type,
            "data": data,
        }
    )


def stream_http_error_event(
    error: AbstractErrorResponse, media_type: str | None = MEDIA_TYPE_JSON
) -> str:
    """Format an SSE error frame for LLM/API failures."""
    logger.error("Error while obtaining answer for user question")
    media_type = media_type or MEDIA_TYPE_JSON
    if media_type == MEDIA_TYPE_TEXT:
        return f"Status: {error.status_code} - {error.detail.response} - {error.detail.cause}"

    return format_stream_data(
        {
            "event": "error",
            "data": {
                "status_code": error.status_code,
                "response": error.detail.response,
                "cause": error.detail.cause,
            },
        }
    )
