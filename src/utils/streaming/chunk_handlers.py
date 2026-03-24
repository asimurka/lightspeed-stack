"""Handlers for processing Responses API stream chunks into SSE frames."""

from collections.abc import Callable
from typing import cast

from llama_stack_api import (
    OpenAIResponseObject,
    OpenAIResponseObjectStream,
    OpenAIResponseObjectStreamResponseCompleted as ResponseCompletedChunk,
    OpenAIResponseObjectStreamResponseMcpCallArgumentsDone as MCPArgsDoneChunk,
    OpenAIResponseObjectStreamResponseOutputItemAdded as OutputItemAddedChunk,
    OpenAIResponseObjectStreamResponseOutputItemDone as OutputItemDoneChunk,
    OpenAIResponseObjectStreamResponseOutputTextDelta as TextDeltaChunk,
    OpenAIResponseObjectStreamResponseOutputTextDone as TextDoneChunk,
    OpenAIResponseOutputMessageMCPCall as MCPCall,
)
from constants import (
    LLM_TOKEN_EVENT,
    LLM_TOOL_CALL_EVENT,
    LLM_TOOL_RESULT_EVENT,
    LLM_TURN_COMPLETE_EVENT,
)
from models.responses import InternalServerErrorResponse, PromptTooLongResponse
from utils.tool_handlers import (
    TOOL_CALL_BUILDERS,
    TOOL_RESULT_BUILDERS,
    build_mcp_tool_call_from_arguments_done,
)
from utils.streaming.events import stream_event, stream_http_error_event
from utils.streaming.stream_state import StreamProcessingState

ChunkHandler = Callable[
    [StreamProcessingState, OpenAIResponseObjectStream],
    list[str],
]


def handle_content_part_added(
    state: StreamProcessingState, _chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Emit an initial empty token to start the stream."""
    out = stream_event(
        {"id": state.chunk_id, "token": ""},
        LLM_TOKEN_EVENT,
        state.media_type,
    )
    state.chunk_id += 1
    return [out]


def handle_output_item_added(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Store MCP call metadata (id, name) for later argument handling."""
    item_added_chunk = cast(OutputItemAddedChunk, chunk)
    if item_added_chunk.item.type == "mcp_call":
        mcp_call_item = cast(MCPCall, item_added_chunk.item)
        state.pending_mcp_calls[item_added_chunk.output_index] = (
            mcp_call_item.id,
            mcp_call_item.name,
        )
    return []


def handle_output_text_delta(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Append and emit a streamed text token."""
    delta_chunk = cast(TextDeltaChunk, chunk)
    state.text_parts.append(delta_chunk.delta)
    out = stream_event(
        {"id": state.chunk_id, "token": delta_chunk.delta},
        LLM_TOKEN_EVENT,
        state.media_type,
    )
    state.chunk_id += 1
    return [out]


def handle_output_text_done(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Store final text for this segment (may be finalized again on completion)."""
    text_done_chunk = cast(TextDoneChunk, chunk)
    state.turn_summary.llm_response = text_done_chunk.text
    return []


def handle_mcp_call_arguments_done(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Build and emit an MCP tool call once all arguments are received."""
    mcp_arguments_done_chunk = cast(MCPArgsDoneChunk, chunk)
    item_info = state.pending_mcp_calls.get(mcp_arguments_done_chunk.output_index)
    if not item_info:
        return []

    tool_call = build_mcp_tool_call_from_arguments_done(
        item_info,
        mcp_arguments_done_chunk.arguments,
    )
    # remove from dict to indicate it was processed during arguments.done
    del state.pending_mcp_calls[mcp_arguments_done_chunk.output_index]
    state.turn_summary.tool_calls.append(tool_call)
    return [
        stream_event(
            tool_call.model_dump(),
            LLM_TOOL_CALL_EVENT,
            state.media_type,
        )
    ]


def handle_output_item_done(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Emit tool call and/or result events when an output item completes."""
    output_item_done_chunk = cast(OutputItemDoneChunk, chunk)
    item = output_item_done_chunk.item
    output_index = output_item_done_chunk.output_index
    frames: list[str] = []

    tool_call_builder = TOOL_CALL_BUILDERS.get(item.type)
    tool_result_builder = TOOL_RESULT_BUILDERS.get(item.type)
    skip_tool_call = (  # skip mcp call if it was already emitted from arguments.done
        item.type == "mcp_call" and output_index not in state.pending_mcp_calls
    )
    tool_call = (
        tool_call_builder(item) if tool_call_builder and not skip_tool_call else None
    )
    tool_result = tool_result_builder(item) if tool_result_builder else None

    if tool_call:
        state.turn_summary.tool_calls.append(tool_call)
        frames.append(
            stream_event(
                tool_call.model_dump(),
                LLM_TOOL_CALL_EVENT,
                state.media_type,
            )
        )
    if tool_result:
        state.turn_summary.tool_results.append(tool_result)
        frames.append(
            stream_event(
                tool_result.model_dump(),
                LLM_TOOL_RESULT_EVENT,
                state.media_type,
            )
        )
    return frames


def handle_response_completed(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Finalize accumulated text and emit the turn-complete event."""
    completed_chunk = cast(ResponseCompletedChunk, chunk)
    state.latest_response_object = completed_chunk.response
    state.turn_summary.llm_response = state.turn_summary.llm_response or "".join(
        state.text_parts
    )
    out = stream_event(
        {
            "id": state.chunk_id,
            "token": state.turn_summary.llm_response,
        },
        LLM_TURN_COMPLETE_EVENT,
        state.media_type,
    )
    state.chunk_id += 1
    return [out]


def handle_response_incomplete_or_failed(
    state: StreamProcessingState, chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Convert incomplete/failed responses into a structured error event."""
    state.latest_response_object = cast(
        OpenAIResponseObject, getattr(chunk, "response")  # noqa: B009
    )
    latest = state.latest_response_object
    error_message = (
        latest.error.message
        if latest.error
        else "An unexpected error occurred while processing the request."
    )
    error_response = (
        PromptTooLongResponse(model=state.context.model_id)
        if "context_length" in error_message.lower()
        else InternalServerErrorResponse.query_failed(error_message)
    )
    return [stream_http_error_event(error_response, state.media_type)]


def handle_unknown_chunk(
    _state: StreamProcessingState, _chunk: OpenAIResponseObjectStream
) -> list[str]:
    """Ignore unrecognized chunk types."""
    return []


CHUNK_HANDLERS: dict[str, ChunkHandler] = {
    "response.content_part.added": handle_content_part_added,
    "response.output_item.added": handle_output_item_added,
    "response.output_text.delta": handle_output_text_delta,
    "response.output_text.done": handle_output_text_done,
    "response.mcp_call.arguments.done": handle_mcp_call_arguments_done,
    "response.output_item.done": handle_output_item_done,
    "response.completed": handle_response_completed,
    "response.incomplete": handle_response_incomplete_or_failed,
    "response.failed": handle_response_incomplete_or_failed,
}


def build_sse_frames_from_chunk(
    state: StreamProcessingState,
    chunk: OpenAIResponseObjectStream,
) -> list[str]:
    """Dispatch a stream chunk to its handler and return SSE frames.

    Args:
        state: Mutable per-request streaming state.
        chunk: Incoming Responses API stream event.

    Returns:
        List of SSE frame strings to emit for this chunk.
    """
    chunk_handler = CHUNK_HANDLERS.get(chunk.type, handle_unknown_chunk)
    return chunk_handler(state, chunk)
