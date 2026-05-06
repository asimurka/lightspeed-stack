"""Dispatchers for streaming response chunks."""

from dataclasses import replace
from functools import singledispatch
from typing import cast

from llama_stack_api import OpenAIResponseObjectStream
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseCompleted as CompletedChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseContentPartAdded as ContentPartAddedChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseFailed as FailedChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseIncomplete as IncompleteChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseMcpCallArgumentsDone as MCPArgsDoneChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseOutputItemAdded as OutputItemAddedChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseOutputItemDone as OutputItemDoneChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseOutputTextDelta as TextDeltaChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseObjectStreamResponseOutputTextDone as TextDoneChunk,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageMCPCall as MCPCall,
)

from log import get_logger
from models.common.turn_summary import ToolCallSummary
from utils.responses import parse_arguments_string
from utils.streaming.events import (
    emit_error_event_from_response,
    serialize_event,
)
from utils.streaming.output_item_dispatchers import dispatch_output_item_done
from utils.streaming.stream_payloads import (
    LlmTokenChunkData,
    LlmTokenStreamPayload,
    LlmToolCallStreamPayload,
    LlmTurnCompleteStreamPayload,
)
from utils.streaming.state import ChunkDispatchResult, StreamDispatchState

logger = get_logger(__name__)

@singledispatch
def dispatch_stream_chunk(
    chunk: OpenAIResponseObjectStream,
    state: StreamDispatchState,
    _media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Fallback dispatcher for unknown chunk types."""
    logger.debug(
        "Ignoring unsupported chunk type=%s",
        getattr(chunk, "type", None),
    )
    return ChunkDispatchResult(state=state)


@dispatch_stream_chunk.register
def _(
    _chunk: ContentPartAddedChunk,
    state: StreamDispatchState,
    media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Handle content part start by emitting an empty token."""
    next_state = replace(state, chunk_id=state.chunk_id + 1)
    token_event = serialize_event(
        LlmTokenStreamPayload(data=LlmTokenChunkData(id=state.chunk_id, token="")),
        media_type,
    )
    return ChunkDispatchResult(state=next_state, events=[token_event])


@dispatch_stream_chunk.register
def _(
    chunk: OutputItemAddedChunk,
    state: StreamDispatchState,
    _media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Track MCP call metadata for arguments.done events."""
    if chunk.item.type != "mcp_call":
        return ChunkDispatchResult(state=state)

    mcp_call_item = cast(MCPCall, chunk.item)
    next_mcp_calls = dict(state.mcp_calls)
    next_mcp_calls[chunk.output_index] = (mcp_call_item.id, mcp_call_item.name)
    return ChunkDispatchResult(state=replace(state, mcp_calls=next_mcp_calls))


@dispatch_stream_chunk.register
def _(
    chunk: TextDeltaChunk,
    state: StreamDispatchState,
    media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Handle token delta chunks."""
    next_text_parts = [*state.text_parts, chunk.delta]
    next_state = replace(
        state,
        chunk_id=state.chunk_id + 1,
        text_parts=next_text_parts,
    )
    token_event = serialize_event(
        LlmTokenStreamPayload(
            data=LlmTokenChunkData(id=state.chunk_id, token=chunk.delta),
        ),
        media_type,
    )
    return ChunkDispatchResult(state=next_state, events=[token_event])


@dispatch_stream_chunk.register
def _(
    chunk: TextDoneChunk,
    state: StreamDispatchState,
    _media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Store final generated text from output_text.done."""
    return ChunkDispatchResult(state=replace(state, llm_response=chunk.text))


@dispatch_stream_chunk.register
def _(
    chunk: MCPArgsDoneChunk,
    state: StreamDispatchState,
    media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Emit MCP tool call when arguments are complete."""
    next_mcp_calls = dict(state.mcp_calls)
    item_info = next_mcp_calls.pop(chunk.output_index, None)
    if item_info is None:
        return ChunkDispatchResult(state=replace(state, mcp_calls=next_mcp_calls))

    item_id, item_name = item_info
    tool_call = ToolCallSummary(
        id=item_id,
        name=item_name,
        args=parse_arguments_string(chunk.arguments),
        type="mcp_call",
    )
    next_state = replace(
        state,
        mcp_calls=next_mcp_calls,
        tool_calls=[*state.tool_calls, tool_call],
    )
    tool_call_event = serialize_event(
        LlmToolCallStreamPayload(data=tool_call),
        media_type,
    )
    return ChunkDispatchResult(state=next_state, events=[tool_call_event])


@dispatch_stream_chunk.register
def _(
    chunk: OutputItemDoneChunk,
    state: StreamDispatchState,
    media_type: str,
    model_id: str,
) -> ChunkDispatchResult:
    """Handle output item completion for tool calls and results."""
    return dispatch_output_item_done(
        chunk.item,
        chunk.output_index,
        state,
        media_type,
        model_id,
    )


@dispatch_stream_chunk.register
def _(
    chunk: CompletedChunk,
    state: StreamDispatchState,
    media_type: str,
    _model_id: str,
) -> ChunkDispatchResult:
    """Handle successful response completion."""
    final_text = state.llm_response or "".join(state.text_parts)
    next_state = replace(
        state,
        chunk_id=state.chunk_id + 1,
        latest_response_object=chunk.response,
        llm_response=final_text,
    )
    complete_event = serialize_event(
        LlmTurnCompleteStreamPayload(
            data=LlmTokenChunkData(id=state.chunk_id, token=final_text),
        ),
        media_type,
    )
    return ChunkDispatchResult(state=next_state, events=[complete_event])


@dispatch_stream_chunk.register
def _(
    chunk: IncompleteChunk | FailedChunk,
    state: StreamDispatchState,
    _media_type: str,
    model_id: str,
) -> ChunkDispatchResult:
    """Handle incomplete or failed response."""
    next_state = replace(state, latest_response_object=chunk.response)
    error_event = emit_error_event_from_response(model_id, chunk.response)
    return ChunkDispatchResult(state=next_state, events=[error_event])
