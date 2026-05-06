"""Shared streaming event formatting utilities."""

import json
from typing import Optional

from llama_stack_api import OpenAIResponseObject

from constants import MEDIA_TYPE_JSON, MEDIA_TYPE_TEXT
from log import get_logger
from models.api.responses.error import (
    AbstractErrorResponse,
    InternalServerErrorResponse,
    PromptTooLongResponse,
)
from models.common.turn_summary import ReferencedDocument
from utils.query import is_context_length_error
from utils.token_counter import TokenCounter
from utils.streaming.stream_payloads import (
    EndEventData,
    EndStreamPayload,
    ErrorEventData,
    ErrorStreamPayload,
    InterruptedEventData,
    InterruptedStreamPayload,
    LlmTokenStreamPayload,
    LlmToolCallStreamPayload,
    LlmToolResultStreamPayload,
    LlmTurnCompleteStreamPayload,
    StartEventData,
    StartStreamPayload,
    StreamLlmEventPayload,
    StreamPayloadBase,
)

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
    if resolved_media_type == MEDIA_TYPE_TEXT:
        cause = error.detail.cause
        cause_part = cause if cause is not None else ""
        return (
            f"Status: {error.status_code} - {error.detail.response} - {cause_part}"
        )
    return format_stream_data(
        ErrorStreamPayload(
            data=ErrorEventData(
                status_code=error.status_code,
                response=error.detail.response,
                cause=error.detail.cause,
            ),
        )
    )


def serialize_start_event(conversation_id: str, request_id: str) -> str:
    """Serialize the stream start payload to an SSE line."""
    return format_stream_data(
        StartStreamPayload(
            data=StartEventData(
                conversation_id=conversation_id,
                request_id=request_id,
            ),
        )
    )


def serialize_interrupted_event(request_id: str) -> str:
    """Serialize an interrupted-stream payload to an SSE line."""
    return format_stream_data(
        InterruptedStreamPayload(
            data=InterruptedEventData(request_id=request_id),
        )
    )


def serialize_end_event(
    token_usage: TokenCounter,
    available_quotas: dict[str, int],
    referenced_documents: list[ReferencedDocument],
    media_type: Optional[str] = None,
) -> str:
    """Serialize the stream end payload for JSON SSE or plain-text clients."""
    resolved_media_type = media_type or MEDIA_TYPE_JSON
    if resolved_media_type == MEDIA_TYPE_TEXT:
        ref_docs_string = "\n".join(
            f"{doc.doc_title}: {doc.doc_url}"
            for doc in referenced_documents
            if doc.doc_url and doc.doc_title
        )
        return f"\n\n---\n\n{ref_docs_string}" if ref_docs_string else ""

    return format_stream_data(
        EndStreamPayload(
            data=EndEventData(
                referenced_documents=referenced_documents,
                truncated=None,
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens,
            ),
            available_quotas=available_quotas,
        )
    )


def serialize_event(
    payload: StreamLlmEventPayload,
    media_type: str = MEDIA_TYPE_JSON,
) -> str:
    """Serialize an LLM stream payload (token, tool, turn complete) for the client."""
    if media_type == MEDIA_TYPE_TEXT:
        if isinstance(payload, LlmTokenStreamPayload):
            return str(payload.data.token)
        if isinstance(payload, LlmTurnCompleteStreamPayload):
            return ""
        if isinstance(payload, LlmToolCallStreamPayload):
            return f"[Tool Call: {payload.data.name}]\n"
        if isinstance(payload, LlmToolResultStreamPayload):
            return "[Tool Result]\n"
        return ""

    return format_stream_data(payload)


def emit_error_event_from_response(
    model_id: str,
    response: OpenAIResponseObject,
) -> str:
    """Build an HTTP error SSE event from a failed response object."""
    error_message = (
        response.error.message
        if response.error
        else "An unexpected error occurred while processing the request."
    )
    error_response = (
        PromptTooLongResponse(model=model_id)
        if is_context_length_error(error_message)
        else InternalServerErrorResponse.query_failed(error_message)
    )
    return serialize_http_error_event(error_response)
