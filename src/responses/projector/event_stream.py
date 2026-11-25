"""PAI ``UIEventStream`` that projects agent-run events into OpenResponses."""

# pylint: disable=too-many-lines

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic_ai.messages import (
    DeferredToolRequestsEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent
from pydantic_ai.ui import UIEventStream

from responses.models.config import (
    ResponseError,
    ResponsePrompt,
    ResponseReasoning,
    ResponseText,
    ResponseUsage,
)
from responses.models.content import OutputTextPart, RefusalPart, StreamTextPart
from responses.models.events import (
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFileSearchCallCompletedEvent,
    ResponseFileSearchCallInProgressEvent,
    ResponseFileSearchCallSearchingEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseIncompleteEvent,
    ResponseInProgressEvent,
    ResponseMcpCallArgumentsDeltaEvent,
    ResponseMcpCallArgumentsDoneEvent,
    ResponseMcpCallCompletedEvent,
    ResponseMcpCallFailedEvent,
    ResponseMcpCallInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputTextAnnotationAddedEvent,
    ResponseOutputTextDeltaEvent,
    ResponseOutputTextDoneEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningTextDoneEvent,
    ResponseStreamEvent,
)
from responses.models.items import (
    FileSearchToolCall,
    FunctionToolCall,
    McpCall,
    ReasoningContent,
    ReasoningItem,
    ReasoningSummary,
    ResponseMessage,
    ResponseOutput,
)
from responses.models.response import ResponseObject
from responses.models.tools import OutputTool, ToolChoice
from responses.projector.classify import (
    KNOWLEDGE_TOOL_NAME,
    ProjectedToolKind,
    classify_tool,
)
from responses.projector.filtering import (
    is_server_managed_output_item,
    should_filter_stream_event,
)
from responses.projector.knowledge import (
    PendingFileCitation,
    file_citation_at,
    file_search_queries,
    file_search_results_from_content,
    pending_file_citations_from_content,
)
from responses.projector.payload import (
    arguments_delta_text,
    arguments_json,
    mcp_tool_name,
    parse_arguments,
    return_text,
    tool_failed,
    usage_from_run,
)
from responses.projector.payload import (
    item_id as response_item_id,
)
from responses.projector.refusal import refusal_message, refusal_stream_events
from responses.projector.run_status import terminal_from_run
from responses.projector.sse import encode_openresponses_event
from responses.projector.state import OpenItem

_ResponseStatus = Literal["in_progress", "completed", "failed", "incomplete"]


# pylint: disable=too-many-instance-attributes,too-many-public-methods
@dataclass
class OpenResponsesEventStream(UIEventStream[None, ResponseStreamEvent, Any, Any]):
    """Transform PAI native agent events into OpenResponses stream events.

    This class does not build or run an agent. Callers feed
    ``run_stream_events`` output into ``transform_stream``. ``stream=true``
    encodes those events as SSE; ``stream=false`` consumes the same iterator
    and reads ``final_response``.
    """

    response_id: str = ""
    model: str = ""
    conversation: Optional[str] = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    available_quotas: dict[str, int] = field(default_factory=dict)
    filter_server_tools: bool = False
    configured_mcp_labels: frozenset[str] = field(default_factory=frozenset)
    client_tool_types: frozenset[str] = field(default_factory=frozenset)
    mcp_tool_servers: dict[str, str] = field(default_factory=dict)
    knowledge_tool_name: str = KNOWLEDGE_TOOL_NAME
    include_file_search_results: bool = True
    instructions: Optional[str] = None
    temperature: Optional[float] = None
    parallel_tool_calls: bool = True
    previous_response_id: Optional[str] = None
    store: Optional[bool] = None
    metadata: Optional[dict[str, str]] = None
    tools: Optional[Sequence[OutputTool]] = None
    tool_choice: Optional[ToolChoice] = None
    reasoning: Optional[ResponseReasoning] = None
    text: Optional[ResponseText] = None
    max_output_tokens: Optional[int] = None
    max_tool_calls: Optional[int] = None
    safety_identifier: Optional[str] = None
    prompt_cache_key: Optional[str] = None
    prompt: Optional[ResponsePrompt] = None

    _sequence: int = field(default=0, init=False, repr=False)
    _status: _ResponseStatus = field(default="in_progress", init=False, repr=False)
    _output: list[ResponseOutput] = field(default_factory=list, init=False, repr=False)
    _open_items: dict[str, OpenItem] = field(
        default_factory=dict, init=False, repr=False
    )
    _open_by_index: dict[int, OpenItem] = field(
        default_factory=dict, init=False, repr=False
    )
    _current_message: Optional[OpenItem] = field(default=None, init=False, repr=False)
    _current_reasoning: Optional[OpenItem] = field(default=None, init=False, repr=False)
    _hidden_output_indices: set[int] = field(
        default_factory=set, init=False, repr=False
    )
    _error: Optional[ResponseError] = field(default=None, init=False, repr=False)
    _completed_at: Optional[int] = field(default=None, init=False, repr=False)
    _usage: Optional[ResponseUsage] = field(default=None, init=False, repr=False)
    _lifecycle_started: bool = field(default=False, init=False, repr=False)
    _pending_citations: list[PendingFileCitation] = field(
        default_factory=list, init=False, repr=False
    )

    def encode_event(self, event: ResponseStreamEvent) -> str:
        """Encode one OpenResponses event as an SSE chunk."""
        return encode_openresponses_event(event)

    @property
    def final_response(self) -> ResponseObject:
        """Client-facing response built from the same projected items as SSE."""
        return self._response_snapshot()

    async def consume(self, stream: AsyncIterator[Any]) -> ResponseObject:
        """Drain ``transform_stream`` and return the buffered final response.

        Args:
            stream: Native PAI agent-run events.

        Returns:
            The same ``ResponseObject`` yielded on ``response.completed`` or
            ``response.failed``.

        """
        async for _ in self.transform_stream(stream):
            pass
        return self.final_response

    async def emit_refusal(self, text: str) -> AsyncIterator[ResponseStreamEvent]:
        """Emit a completed refusal (shields / question validity).

        Call instead of ``transform_stream`` when the run is blocked before
        the agent loop. Yields created, in_progress, refusal item events, and
        completed.

        Args:
            text: Refusal text shown to the client.

        Yields:
            OpenResponses events for the blocked turn.

        """
        if not self._lifecycle_started:
            async for event in self.before_stream():
                yield event
        extra = self._open_refusal(text)
        self._status = "completed"
        self._completed_at = int(time.time())
        for event in self._emit([*extra, *self._terminal_events("completed")]):
            yield event

    async def emit_error(
        self, message: str, code: Optional[str] = None
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Emit a transport ``error`` event and mark the response failed.

        Args:
            message: Error text.
            code: Optional machine-readable error code.

        Yields:
            A single ``error`` event.

        """
        self._status = "failed"
        self._completed_at = int(time.time())
        self._error = ResponseError(
            code=code or "server_error", message=message or "error"
        )
        for event in self._emit(
            [
                ResponseErrorEvent(
                    message=message or "error",
                    code=code,
                    sequence_number=0,
                )
            ]
        ):
            yield event

    async def before_stream(self) -> AsyncIterator[ResponseStreamEvent]:
        """Emit ``response.created`` then ``response.in_progress``."""
        self._lifecycle_started = True
        self._status = "in_progress"
        for event in self._emit(
            [
                ResponseCreatedEvent(
                    response=self._response_snapshot(), sequence_number=0
                ),
                ResponseInProgressEvent(
                    response=self._response_snapshot(), sequence_number=0
                ),
            ]
        ):
            yield event

    async def handle_text_start(
        self, part: TextPart, follows_text: bool = False
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Open a message item and output-text content part."""
        for event in self._emit(self._on_text_start(part, follows_text)):
            yield event

    async def handle_text_delta(
        self, delta: TextPartDelta
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Project a text delta onto ``response.output_text.delta``."""
        for event in self._emit(self._on_text_delta(delta)):
            yield event

    async def handle_text_end(
        self, part: TextPart, followed_by_text: bool = False
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Close the current message item when the text part is finished."""
        for event in self._emit(self._on_text_end(part, followed_by_text)):
            yield event

    async def handle_thinking_start(
        self, part: ThinkingPart, follows_thinking: bool = False
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Open a reasoning output item."""
        for event in self._emit(self._on_thinking_start(part, follows_thinking)):
            yield event

    async def handle_thinking_delta(
        self, delta: ThinkingPartDelta
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Project thinking text onto ``response.reasoning_text.delta``."""
        for event in self._emit(self._on_thinking_delta(delta)):
            yield event

    async def handle_thinking_end(
        self, part: ThinkingPart, followed_by_thinking: bool = False
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Close the current reasoning item."""
        for event in self._emit(self._on_thinking_end(part, followed_by_thinking)):
            yield event

    async def handle_tool_call_start(
        self, part: ToolCallPart
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Open a function, MCP, or file-search output item."""
        for event in self._emit(self._on_tool_call_start(part)):
            yield event

    async def handle_tool_call_delta(
        self, delta: ToolCallPartDelta
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Project streamed tool-call arguments."""
        for event in self._emit(self._on_tool_call_delta(delta)):
            yield event

    async def handle_tool_call_end(
        self, part: ToolCallPart
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Finish streamed tool-call arguments."""
        for event in self._emit(self._on_tool_call_end(part)):
            yield event

    async def handle_function_tool_call(
        self, event: FunctionToolCallEvent
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Mark in-loop file search as searching once the call is dispatched."""
        for item_event in self._emit(self._on_function_tool_call(event)):
            yield item_event

    async def handle_function_tool_result(
        self, event: FunctionToolResultEvent
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Complete in-loop MCP, file-search, or generic function items."""
        for item_event in self._emit(self._on_function_tool_result(event)):
            yield item_event

    async def handle_deferred_tool_requests(
        self, event: DeferredToolRequestsEvent
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Complete deferred client tools as ``function_call`` items."""
        for item_event in self._emit(self._on_deferred_tool_requests(event)):
            yield item_event

    async def handle_run_result(
        self, event: AgentRunResultEvent
    ) -> AsyncIterator[ResponseStreamEvent]:
        """Emit the terminal response event from the agent run result."""
        status, error, refusal_text = terminal_from_run(event.result)
        extra: list[ResponseStreamEvent] = []
        if refusal_text and not self._has_assistant_message():
            extra = self._open_refusal(refusal_text)
        self._complete_from_result(event.result, status=status, error=error)
        for item_event in self._emit([*extra, *self._terminal_events(status)]):
            yield item_event

    async def on_error(self, error: Exception) -> AsyncIterator[ResponseStreamEvent]:
        """Emit ``response.failed`` for a mid-run error."""
        self._status = "failed"
        self._completed_at = int(time.time())
        self._error = ResponseError(
            code="server_error", message=str(error) or error.__class__.__name__
        )
        for item_event in self._emit(
            [ResponseFailedEvent(response=self._response_snapshot(), sequence_number=0)]
        ):
            yield item_event

    async def on_cancelled(self, cancelled: Any) -> AsyncIterator[ResponseStreamEvent]:
        """Emit ``response.incomplete`` when the run is cancelled."""
        self._status = "incomplete"
        self._completed_at = int(time.time())
        for item_event in self._emit(
            [
                ResponseIncompleteEvent(
                    response=self._response_snapshot(), sequence_number=0
                )
            ]
        ):
            yield item_event

    def _on_text_start(
        self, part: TextPart, follows_text: bool
    ) -> list[ResponseStreamEvent]:
        """Open a message output item unless this part continues one."""
        if follows_text and self._current_message is not None:
            self._current_message.text += part.content
            return []

        item_id = part.id or f"msg_{self.response_id}_{len(self._output)}"
        message = ResponseMessage(
            type="message",
            role="assistant",
            content=[OutputTextPart(text=part.content)],
            id=item_id,
            status="in_progress",
        )
        opened = self._register_item(
            message, kind="message", item_id=item_id, text=part.content
        )
        self._current_message = opened
        part_payload = StreamTextPart(text=part.content)
        return [
            ResponseOutputItemAddedEvent(
                response_id=self.response_id,
                item=message,
                output_index=opened.output_index,
                sequence_number=0,
            ),
            ResponseContentPartAddedEvent(
                content_index=opened.content_index,
                response_id=self.response_id,
                item_id=item_id,
                output_index=opened.output_index,
                part=part_payload,
                sequence_number=0,
            ),
        ]

    def _on_text_delta(self, delta: TextPartDelta) -> list[ResponseStreamEvent]:
        """Append streamed text to the open message item."""
        opened = self._current_message
        if opened is None:
            return []
        chunk = delta.content_delta or ""
        opened.text += chunk
        item_id = opened.item.id or ""
        self._replace_message_text(opened)
        return [
            ResponseOutputTextDeltaEvent(
                content_index=opened.content_index,
                delta=chunk,
                item_id=item_id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]

    def _on_text_end(
        self, part: TextPart, followed_by_text: bool
    ) -> list[ResponseStreamEvent]:
        """Close the message item when no further text part follows."""
        if followed_by_text:
            return []
        opened = self._current_message
        if opened is None:
            return []
        text = part.content or opened.text
        opened.text = text
        events: list[ResponseStreamEvent] = [
            ResponseOutputTextDoneEvent(
                content_index=opened.content_index,
                text=text,
                item_id=opened.item.id or "",
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]
        events.extend(self._attach_pending_citations(opened, text))
        self._replace_message_text(opened, status="completed")
        item_id = opened.item.id or ""
        done_part = StreamTextPart(text=text, annotations=list(opened.annotations))
        events.extend(
            [
                ResponseContentPartDoneEvent(
                    content_index=opened.content_index,
                    response_id=self.response_id,
                    item_id=item_id,
                    output_index=opened.output_index,
                    part=done_part,
                    sequence_number=0,
                ),
                ResponseOutputItemDoneEvent(
                    response_id=self.response_id,
                    item=opened.item,
                    output_index=opened.output_index,
                    sequence_number=0,
                ),
            ]
        )
        opened.done = True
        self._current_message = None
        return events

    def _on_thinking_start(
        self, part: ThinkingPart, follows_thinking: bool
    ) -> list[ResponseStreamEvent]:
        """Open a reasoning item for a thinking part."""
        if follows_thinking and self._current_reasoning is not None:
            self._current_reasoning.text += part.content
            return []
        item_id = part.id or f"rs_{self.response_id}_{len(self._output)}"
        item = ReasoningItem(
            type="reasoning",
            id=item_id,
            summary=[ReasoningSummary(text=part.content)],
            content=[ReasoningContent(text=part.content)],
            status="in_progress",
        )
        opened = self._register_item(
            item, kind="reasoning", item_id=item_id, text=part.content
        )
        self._current_reasoning = opened
        return [
            ResponseOutputItemAddedEvent(
                response_id=self.response_id,
                item=item,
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]

    def _on_thinking_delta(self, delta: ThinkingPartDelta) -> list[ResponseStreamEvent]:
        """Append thinking text to the open reasoning item."""
        opened = self._current_reasoning
        if opened is None:
            return []
        chunk = delta.content_delta or ""
        opened.text += chunk
        item_id = response_item_id(opened.item)
        return [
            ResponseReasoningTextDeltaEvent(
                content_index=opened.content_index,
                delta=chunk,
                item_id=item_id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]

    def _on_thinking_end(
        self, part: ThinkingPart, followed_by_thinking: bool
    ) -> list[ResponseStreamEvent]:
        """Close the reasoning item when thinking is finished."""
        if followed_by_thinking:
            return []
        opened = self._current_reasoning
        if opened is None:
            return []
        text = part.content or opened.text
        opened.text = text
        item = ReasoningItem(
            type="reasoning",
            id=response_item_id(opened.item),
            summary=[ReasoningSummary(text=text)],
            content=[ReasoningContent(text=text)],
            status="completed",
        )
        self._store_item(opened, item)
        events: list[ResponseStreamEvent] = [
            ResponseReasoningTextDoneEvent(
                content_index=opened.content_index,
                text=text,
                item_id=response_item_id(item),
                output_index=opened.output_index,
                sequence_number=0,
            ),
            ResponseOutputItemDoneEvent(
                response_id=self.response_id,
                item=item,
                output_index=opened.output_index,
                sequence_number=0,
            ),
        ]
        opened.done = True
        self._current_reasoning = None
        return events

    def _on_tool_call_start(self, part: ToolCallPart) -> list[ResponseStreamEvent]:
        """Open a typed or generic tool-call output item."""
        kind, server_label = classify_tool(
            part.tool_name, self.mcp_tool_servers, self.knowledge_tool_name
        )
        arguments = arguments_json(part.args)
        item = self._build_tool_item(kind, part, arguments, server_label)
        opened = self._register_item(
            item,
            kind=kind,
            item_id=part.tool_call_id,
            tool_call_id=part.tool_call_id,
            arguments=arguments,
        )
        events: list[ResponseStreamEvent] = [
            ResponseOutputItemAddedEvent(
                response_id=self.response_id,
                item=item,
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]
        events.extend(self._tool_start_progress(kind, opened))
        if kind != ProjectedToolKind.FILE_SEARCH and arguments and arguments != "{}":
            events.append(self._arguments_delta(kind, opened, arguments))
        return events

    def _on_tool_call_delta(
        self, delta: ToolCallPartDelta
    ) -> list[ResponseStreamEvent]:
        """Append argument deltas onto the matching open tool item."""
        opened = self._open_for_delta(delta)
        if opened is None:
            return []
        chunk = arguments_delta_text(delta.args_delta)
        if not chunk:
            return []
        opened.arguments += chunk if isinstance(delta.args_delta, str) else ""
        if not isinstance(delta.args_delta, str):
            opened.arguments = chunk
        self._refresh_tool_arguments(opened)
        if opened.kind == ProjectedToolKind.FILE_SEARCH:
            return []
        if opened.kind not in (ProjectedToolKind.MCP, ProjectedToolKind.FUNCTION):
            return []
        return [self._arguments_delta(opened.kind, opened, chunk)]

    def _on_tool_call_end(self, part: ToolCallPart) -> list[ResponseStreamEvent]:
        """Emit arguments-done for the finished tool-call part."""
        opened = self._open_items.get(part.tool_call_id)
        if opened is None:
            return []
        opened.arguments = arguments_json(part.args) or opened.arguments
        self._refresh_tool_arguments(opened)
        if opened.kind == ProjectedToolKind.FILE_SEARCH:
            return []
        if opened.kind not in (ProjectedToolKind.MCP, ProjectedToolKind.FUNCTION):
            return []
        return [self._arguments_done(opened.kind, opened)]

    def _on_function_tool_call(
        self, event: FunctionToolCallEvent
    ) -> list[ResponseStreamEvent]:
        """Emit file-search searching once the in-loop call is dispatched."""
        opened = self._open_items.get(event.part.tool_call_id)
        if opened is None or opened.kind != ProjectedToolKind.FILE_SEARCH:
            return []
        return [
            ResponseFileSearchCallSearchingEvent(
                item_id=response_item_id(opened.item),
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]

    def _on_function_tool_result(
        self, event: FunctionToolResultEvent
    ) -> list[ResponseStreamEvent]:
        """Complete an in-loop tool item from its return or retry prompt."""
        part = event.part
        tool_call_id = part.tool_call_id
        opened = self._open_items.get(tool_call_id)
        if opened is None or opened.done:
            return []
        failed = tool_failed(part)
        if opened.kind == ProjectedToolKind.MCP:
            return self._complete_mcp(opened, part, failed)
        if opened.kind == ProjectedToolKind.FILE_SEARCH:
            return self._complete_file_search(opened, part, failed)
        return self._complete_function(opened, failed)

    def _on_deferred_tool_requests(
        self, event: DeferredToolRequestsEvent
    ) -> list[ResponseStreamEvent]:
        """Mark deferred client function calls completed for the client."""
        events: list[ResponseStreamEvent] = []
        for call in event.requests.calls:
            opened = self._open_items.get(call.tool_call_id)
            if opened is None or opened.done:
                continue
            events.extend(self._complete_function(opened, failed=False))
        return events

    def _complete_function(
        self, opened: OpenItem, failed: bool
    ) -> list[ResponseStreamEvent]:
        """Finish a generic ``function_call`` item."""
        item = opened.item
        if not isinstance(item, FunctionToolCall):
            return []
        updated = item.model_copy(
            update={"status": "failed" if failed else "completed"}
        )
        self._store_item(opened, updated)
        opened.done = True
        return [
            ResponseOutputItemDoneEvent(
                response_id=self.response_id,
                item=updated,
                output_index=opened.output_index,
                sequence_number=0,
            )
        ]

    def _complete_mcp(
        self,
        opened: OpenItem,
        part: ToolReturnPart | RetryPromptPart,
        failed: bool,
    ) -> list[ResponseStreamEvent]:
        """Finish an ``mcp_call`` item with output or error text."""
        item = opened.item
        if not isinstance(item, McpCall):
            return []
        output = None if failed else return_text(part)
        error = return_text(part) if failed else None
        updated = item.model_copy(update={"output": output, "error": error})
        self._store_item(opened, updated)
        opened.done = True
        progress: ResponseStreamEvent
        if failed:
            progress = ResponseMcpCallFailedEvent(
                item_id=updated.id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        else:
            progress = ResponseMcpCallCompletedEvent(
                item_id=updated.id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        return [
            progress,
            ResponseOutputItemDoneEvent(
                response_id=self.response_id,
                item=updated,
                output_index=opened.output_index,
                sequence_number=0,
            ),
        ]

    def _complete_file_search(
        self,
        opened: OpenItem,
        part: ToolReturnPart | RetryPromptPart,
        failed: bool,
    ) -> list[ResponseStreamEvent]:
        """Finish a ``file_search_call`` item, attaching RAG rows when present."""
        item = opened.item
        if not isinstance(item, FileSearchToolCall):
            return []
        results = None
        if not failed and isinstance(part, ToolReturnPart):
            rows = file_search_results_from_content(part.content)
            if self.include_file_search_results:
                results = rows
            self._pending_citations.extend(
                pending_file_citations_from_content(part.content)
            )
        queries = list(item.queries) or file_search_queries(
            parse_arguments(opened.arguments)
        )
        updated = item.model_copy(
            update={
                "status": "failed" if failed else "completed",
                "results": results,
                "queries": queries,
            }
        )
        self._store_item(opened, updated)
        opened.done = True
        return [
            ResponseFileSearchCallCompletedEvent(
                item_id=updated.id,
                output_index=opened.output_index,
                sequence_number=0,
            ),
            ResponseOutputItemDoneEvent(
                response_id=self.response_id,
                item=updated,
                output_index=opened.output_index,
                sequence_number=0,
            ),
        ]

    def _build_tool_item(
        self,
        kind: ProjectedToolKind,
        part: ToolCallPart,
        arguments: str,
        server_label: Optional[str],
    ) -> ResponseOutput:
        """Create the OpenResponses item for a tool-call part."""
        if kind == ProjectedToolKind.MCP:
            return McpCall(
                type="mcp_call",
                id=part.tool_call_id,
                arguments=arguments,
                name=mcp_tool_name(part.tool_name, server_label),
                server_label=server_label or part.tool_name,
            )
        if kind == ProjectedToolKind.FILE_SEARCH:
            return FileSearchToolCall(
                type="file_search_call",
                id=part.tool_call_id,
                queries=file_search_queries(part.args_as_dict()),
                status="in_progress",
            )
        return FunctionToolCall(
            type="function_call",
            call_id=part.tool_call_id,
            name=part.tool_name,
            arguments=arguments,
            id=part.tool_call_id,
            status="in_progress",
        )

    def _tool_start_progress(
        self, kind: ProjectedToolKind, opened: OpenItem
    ) -> list[ResponseStreamEvent]:
        """Lifecycle events that follow ``output_item.added`` for a tool."""
        item_id = response_item_id(opened.item)
        if kind == ProjectedToolKind.MCP:
            return [
                ResponseMcpCallInProgressEvent(
                    item_id=item_id,
                    output_index=opened.output_index,
                    sequence_number=0,
                )
            ]
        if kind == ProjectedToolKind.FILE_SEARCH:
            return [
                ResponseFileSearchCallInProgressEvent(
                    item_id=item_id,
                    output_index=opened.output_index,
                    sequence_number=0,
                )
            ]
        return []

    def _arguments_delta(
        self,
        kind: ProjectedToolKind | Literal["message", "reasoning"],
        opened: OpenItem,
        delta: str,
    ) -> ResponseStreamEvent:
        """Build an arguments-delta event for function or MCP calls."""
        item_id = response_item_id(opened.item)
        if kind == ProjectedToolKind.MCP:
            return ResponseMcpCallArgumentsDeltaEvent(
                delta=delta,
                item_id=item_id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        return ResponseFunctionCallArgumentsDeltaEvent(
            delta=delta,
            item_id=item_id,
            output_index=opened.output_index,
            sequence_number=0,
        )

    def _arguments_done(
        self,
        kind: ProjectedToolKind | Literal["message", "reasoning"],
        opened: OpenItem,
    ) -> ResponseStreamEvent:
        """Build an arguments-done event for function or MCP calls."""
        item_id = response_item_id(opened.item)
        if kind == ProjectedToolKind.MCP:
            return ResponseMcpCallArgumentsDoneEvent(
                arguments=opened.arguments,
                item_id=item_id,
                output_index=opened.output_index,
                sequence_number=0,
            )
        return ResponseFunctionCallArgumentsDoneEvent(
            arguments=opened.arguments,
            item_id=item_id,
            output_index=opened.output_index,
            sequence_number=0,
        )

    def _register_item(  # pylint: disable=too-many-arguments
        self,
        item: ResponseOutput,
        *,
        kind: ProjectedToolKind | Literal["message", "reasoning"],
        item_id: str,
        tool_call_id: Optional[str] = None,
        arguments: str = "",
        text: str = "",
    ) -> OpenItem:
        """Append an output item and record its streaming state."""
        output_index = len(self._output)
        self._output.append(item)
        hidden = self.filter_server_tools and is_server_managed_output_item(
            item, self.configured_mcp_labels, self.client_tool_types
        )
        if hidden:
            self._hidden_output_indices.add(output_index)
        opened = OpenItem(
            output_index=output_index,
            item=item,
            kind=kind,
            tool_call_id=tool_call_id,
            hidden=hidden,
            arguments=arguments,
            text=text,
        )
        self._open_by_index[output_index] = opened
        self._open_items[tool_call_id or item_id] = opened
        return opened

    def _store_item(self, opened: OpenItem, item: ResponseOutput) -> None:
        """Replace the item stored at an open slot."""
        opened.item = item
        self._output[opened.output_index] = item

    def _replace_message_text(
        self, opened: OpenItem, status: str = "in_progress"
    ) -> None:
        """Write accumulated text onto the open message item."""
        item_id = opened.item.id if isinstance(opened.item, ResponseMessage) else None
        message = ResponseMessage(
            type="message",
            role="assistant",
            content=[
                OutputTextPart(text=opened.text, annotations=list(opened.annotations))
            ],
            id=item_id,
            status=status,
        )
        self._store_item(opened, message)

    def _attach_pending_citations(
        self, opened: OpenItem, text: str
    ) -> list[ResponseStreamEvent]:
        """Attach knowledge citations to an assistant message and emit events."""
        if not self._pending_citations:
            return []
        index = len(text)
        item_id = opened.item.id or ""
        events: list[ResponseStreamEvent] = []
        for annotation_index, pending in enumerate(self._pending_citations):
            annotation = file_citation_at(pending, index)
            opened.annotations.append(annotation)
            events.append(
                ResponseOutputTextAnnotationAddedEvent(
                    item_id=item_id,
                    output_index=opened.output_index,
                    content_index=opened.content_index,
                    annotation_index=annotation_index,
                    annotation=annotation,
                    sequence_number=0,
                )
            )
        self._pending_citations.clear()
        return events

    def _open_refusal(self, text: str) -> list[ResponseStreamEvent]:
        """Register a completed refusal message and return its stream events."""
        item_id = f"msg_{self.response_id}_{len(self._output)}"
        item = refusal_message(item_id, text, "completed")
        opened = self._register_item(item, kind="message", item_id=item_id, text=text)
        opened.done = True
        self._current_message = None
        return refusal_stream_events(
            response_id=self.response_id,
            item=item,
            output_index=opened.output_index,
            text=text,
        )

    def _has_assistant_message(self) -> bool:
        """Return whether any assistant message is already in output."""
        return any(isinstance(item, ResponseMessage) for item in self._client_output())

    def _terminal_events(self, status: _ResponseStatus) -> list[ResponseStreamEvent]:
        """Build the lifecycle event that closes the response."""
        snapshot = self._response_snapshot()
        if status == "failed":
            return [ResponseFailedEvent(response=snapshot, sequence_number=0)]
        if status == "incomplete":
            return [ResponseIncompleteEvent(response=snapshot, sequence_number=0)]
        return [ResponseCompletedEvent(response=snapshot, sequence_number=0)]

    def _refresh_tool_arguments(self, opened: OpenItem) -> None:
        """Keep stored tool items in sync with streamed arguments."""
        item = opened.item
        if isinstance(item, FunctionToolCall):
            self._store_item(
                opened, item.model_copy(update={"arguments": opened.arguments})
            )
        elif isinstance(item, McpCall):
            self._store_item(
                opened, item.model_copy(update={"arguments": opened.arguments})
            )

    def _open_for_delta(self, delta: ToolCallPartDelta) -> Optional[OpenItem]:
        """Find the open tool item for an arguments delta."""
        if delta.tool_call_id and delta.tool_call_id in self._open_items:
            return self._open_items[delta.tool_call_id]
        if len(self._open_items) == 1:
            return next(iter(self._open_items.values()))
        return None

    def _complete_from_result(
        self,
        result: AgentRunResult[Any],
        *,
        status: _ResponseStatus = "completed",
        error: Optional[ResponseError] = None,
    ) -> None:
        """Apply run usage and mark the response terminal."""
        self._status = status
        self._completed_at = int(time.time())
        self._usage = usage_from_run(result.usage)
        if error is not None:
            self._error = error

    def _client_output(self) -> list[ResponseOutput]:
        """Output items visible to the client after server-tool filtering."""
        if not self.filter_server_tools:
            return list(self._output)
        return [
            item
            for index, item in enumerate(self._output)
            if index not in self._hidden_output_indices
        ]

    def _output_text(self) -> str:
        """Concatenate assistant ``output_text`` parts."""
        chunks: list[str] = []
        for item in self._client_output():
            if not isinstance(item, ResponseMessage):
                continue
            content = item.content
            if isinstance(content, str):
                chunks.append(content)
                continue
            for part in content:
                if isinstance(part, OutputTextPart):
                    chunks.append(part.text)
                elif isinstance(part, RefusalPart):
                    chunks.append(part.refusal)
        return "".join(chunks)

    def _response_snapshot(self) -> ResponseObject:
        """Build the current response envelope for lifecycle events."""
        terminal = self._status in {"completed", "failed", "incomplete"}
        return ResponseObject(
            created_at=self.created_at,
            completed_at=self._completed_at,
            error=self._error,
            id=self.response_id,
            model=self.model,
            output=self._client_output(),
            parallel_tool_calls=self.parallel_tool_calls,
            previous_response_id=self.previous_response_id,
            prompt_cache_key=self.prompt_cache_key,
            prompt=self.prompt,
            status=self._status,
            temperature=self.temperature,
            text=self.text,
            tools=self.tools,
            tool_choice=self.tool_choice,
            usage=self._usage,
            instructions=self.instructions,
            max_tool_calls=self.max_tool_calls,
            reasoning=self.reasoning,
            max_output_tokens=self.max_output_tokens,
            safety_identifier=self.safety_identifier,
            metadata=self.metadata,
            store=self.store,
            conversation=self.conversation,
            available_quotas=self.available_quotas if terminal else {},
            output_text=self._output_text() if terminal else "",
        )

    def _emit(
        self, events: Iterable[ResponseStreamEvent]
    ) -> Iterator[ResponseStreamEvent]:
        """Assign sequence numbers and drop filtered server-tool events."""
        for event in events:
            if should_filter_stream_event(
                event, self.filter_server_tools, self._hidden_output_indices
            ):
                continue
            yield event.model_copy(update={"sequence_number": self._take_seq()})

    def _take_seq(self) -> int:
        """Return the next event sequence number."""
        number = self._sequence
        self._sequence += 1
        return number
