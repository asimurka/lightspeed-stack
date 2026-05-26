"""Shared streaming event formatting utilities."""

import json
from typing import Optional

from constants import MEDIA_TYPE_JSON
from log import get_logger
from models.api.responses.error import (
    AbstractErrorResponse,
)
from models.common.streaming import (
    EndEventData,
    EndStreamPayload,
    ErrorEventData,
    ErrorStreamPayload,
    InterruptedEventData,
    InterruptedStreamPayload,
    StartEventData,
    StartStreamPayload,
    StreamEventPayload,
    StreamPayloadBase,
)
from models.common.turn_summary import ReferencedDocument
from utils.token_counter import TokenCounter

logger = get_logger(__name__)


def format_stream_data(data: StreamPayloadBase) -> str:
    """Format a Pydantic payload as an SSE ``data:`` line."""
    return f"data: {json.dumps(data.model_dump(mode='json'))}\n\n"


def serialize_http_error_event(
    error: AbstractErrorResponse,
    media_type: Optional[str] = None,
) -> str:
    """Serialize an API error to an SSE or plain-text client response."""
    logger.error("Error while obtaining answer for user question")
    resolved_media_type = media_type or MEDIA_TYPE_JSON
    payload = ErrorStreamPayload(
        data=ErrorEventData(
            status_code=error.status_code,
            response=error.detail.response,
            cause=error.detail.cause,
        ),
    )
    return serialize_event(payload, resolved_media_type)


def serialize_start_event(
    conversation_id: str,
    request_id: str,
    media_type: str = MEDIA_TYPE_JSON,
) -> str:
    """Serialize the stream start payload to an SSE line."""
    payload = StartStreamPayload(
        data=StartEventData(
            conversation_id=conversation_id,
            request_id=request_id,
        ),
    )
    return serialize_event(payload, media_type)


def serialize_interrupted_event(
    request_id: str, media_type: str = MEDIA_TYPE_JSON
) -> str:
    """Serialize an interrupted-stream payload to an SSE line."""
    payload = InterruptedStreamPayload(
        data=InterruptedEventData(request_id=request_id),
    )
    return serialize_event(payload, media_type)


def serialize_end_event(
    token_usage: TokenCounter,
    available_quotas: dict[str, int],
    referenced_documents: list[ReferencedDocument],
    media_type: Optional[str] = None,
) -> str:
    """Serialize the stream end payload for JSON SSE or plain-text clients."""
    resolved_media_type = media_type or MEDIA_TYPE_JSON
    payload = EndStreamPayload(
        data=EndEventData(
            referenced_documents=referenced_documents,
            truncated=None,
            input_tokens=token_usage.input_tokens,
            output_tokens=token_usage.output_tokens,
        ),
        available_quotas=available_quotas,
    )
    return serialize_event(payload, resolved_media_type)


def serialize_event(
    payload: StreamEventPayload,
    media_type: str = MEDIA_TYPE_JSON,
) -> str:
    """Serialize an LLM stream payload (token, tool, turn complete) for the client."""
    if media_type == MEDIA_TYPE_JSON:
        return payload.serialize_json()
    return payload.serialize_text()
