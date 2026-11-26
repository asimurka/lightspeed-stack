"""Project Pydantic AI agent stream events into OpenResponses events."""

# pylint: disable=too-many-lines

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast

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

from responses.models.config import ResponseError
from responses.models.content import (
    OutputMessageContent,
    OutputTextPart,
    StreamTextPart,
)
from responses.models.events import (
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
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
    ResponseMessage,
    ResponseOutput,
)
from responses.models.response import ResponseObject
from responses.projector.classify import ProjectedToolKind, classify_tool
from responses.projector.filtering import (
    is_server_managed_output_item,
    should_filter_stream_event,
)
from responses.projector.knowledge import (
    file_search_queries,
    file_search_results_from_content,
)
from responses.projector.payload import (
    arguments_delta_text,
    arguments_json,
    mcp_tool_name,
    return_text,
    tool_failed,
    usage_from_run,
)
from responses.projector.policy import ProjectionPolicy
from responses.projector.refusal import refusal_message, refusal_stream_events
from responses.projector.run_status import terminal_from_run
from responses.projector.sse import encode_openresponses_event
from responses.projector.state import (
    ItemTracker,
    OpenTool,
    open_output_text_part,
    open_reasoning_text_part,
)

_ResponseStatus = Literal["in_progress", "completed", "failed", "incomplete"]


# pylint: disable=too-many-public-methods
@dataclass(kw_only=True)
class OpenResponsesEventStream(UIEventStream[None, ResponseStreamEvent, Any, Any]):
    """Maps agent run events to OpenResponses stream events.

    Feed agent stream output into transform_stream. Streaming mode encodes SSE;
    non-streaming mode drains the same stream into final_response. Shield
    skips surface as native PAI part events (start and end, no token deltas).

    The response field is the live envelope; lifecycle events receive a deep
    copy so later edits do not change already-sent payloads.
    """

    response: ResponseObject
    policy: ProjectionPolicy = field(default_factory=ProjectionPolicy)
    in_flight: ItemTracker = field(default_factory=ItemTracker)
    _sequence: int = field(default=0, init=False, repr=False)

    def encode_event(self, event: ResponseStreamEvent) -> str:
        """Encode one OpenResponses event as an SSE chunk."""
        return encode_openresponses_event(event)

    @property
    def final_response(self) -> ResponseObject:
        """Client-facing response built from the same projected items as SSE."""
        return self._snapshot()

    async def consume(self, stream: AsyncIterator[Any]) -> ResponseObject:
        """Drain the agent stream and return the final response envelope.

        Args:
            stream: Native agent run events from Pydantic AI.

        Returns:
            The same response body as on the terminal completed or failed event.

        """
        async for _ in self.transform_stream(stream):
            pass
        return self.final_response

    async def before_stream(self) -> AsyncIterator[ResponseStreamEvent]:
        """Emit response.created and response.in_progress."""
        self.in_flight.lifecycle_started = True
        self.response.status = "in_progress"
        for event in self._emit(
            [
                ResponseCreatedEvent(response=self._snapshot()),
                ResponseInProgressEvent(response=self._snapshot()),
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
        """Emit output text delta events for assistant text."""
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
        """Emit reasoning text delta events."""
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
        """Close deferred client tools as function_call items."""
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
        """Emit response.failed when the agent run errors mid-stream."""
        self._mark_terminal(
            "failed",
            error=ResponseError(
                code="server_error", message=str(error) or error.__class__.__name__
            ),
        )
        for item_event in self._emit([ResponseFailedEvent(response=self._snapshot())]):
            yield item_event

    async def on_cancelled(self, cancelled: Any) -> AsyncIterator[ResponseStreamEvent]:
        """Emit response.incomplete when the run is cancelled."""
        self._mark_terminal("incomplete")
        for item_event in self._emit(
            [ResponseIncompleteEvent(response=self._snapshot())]
        ):
            yield item_event

    def _on_text_start(
        self, part: TextPart, follows_text: bool
    ) -> list[ResponseStreamEvent]:
        """Register a message item, or fold a continuation into the current one."""
        if follows_text:
            self.in_flight.extend_message(part.content)
            return []

        item_id = part.id or f"msg_{self.response.id}_{len(self.response.output)}"
        message = ResponseMessage(
            type="message",
            role="assistant",
            content=[OutputTextPart(text=part.content)],
            id=item_id,
            status="in_progress",
        )
        output_index = self._append_output(message)
        self.in_flight.current_message = message
        part_payload = StreamTextPart(text=part.content)
        return [
            ResponseOutputItemAddedEvent(
                response_id=self.response.id,
                item=message,
                output_index=output_index,
            ),
            ResponseContentPartAddedEvent(
                content_index=0,
                response_id=self.response.id,
                item_id=item_id,
                output_index=output_index,
                part=part_payload,
            ),
        ]

    def _on_text_delta(self, delta: TextPartDelta) -> list[ResponseStreamEvent]:
        """Append streamed text to the current message."""
        message = self.in_flight.current_message
        if message is None or message.id is None:
            return []
        self.in_flight.extend_message(delta.content_delta)
        return [
            ResponseOutputTextDeltaEvent(
                content_index=0,
                delta=delta.content_delta,
                item_id=message.id,
                output_index=self._index(message),
            )
        ]

    def _on_text_end(
        self, _part: TextPart, followed_by_text: bool
    ) -> list[ResponseStreamEvent]:
        """Close the current message when no further text part follows."""
        if followed_by_text:
            return []
        message = self.in_flight.current_message
        if message is None or message.id is None:
            return []
        text_part = open_output_text_part(message)
        text = text_part.text if text_part is not None else ""
        message.status = "completed"
        output_index = self._index(message)
        item_id = message.id
        self.in_flight.current_message = None
        return [
            ResponseOutputTextDoneEvent(
                content_index=0,
                text=text,
                item_id=item_id,
                output_index=output_index,
            ),
            ResponseContentPartDoneEvent(
                content_index=0,
                response_id=self.response.id,
                item_id=item_id,
                output_index=output_index,
                part=StreamTextPart(text=text),
            ),
            ResponseOutputItemDoneEvent(
                response_id=self.response.id,
                item=message,
                output_index=output_index,
            ),
        ]

    def _on_thinking_start(
        self, part: ThinkingPart, follows_thinking: bool
    ) -> list[ResponseStreamEvent]:
        """Register a reasoning item, or fold a continuation into the current one."""
        if follows_thinking:
            self.in_flight.extend_reasoning(part.content)
            return []
        item_id = part.id or f"rs_{self.response.id}_{len(self.response.output)}"
        item = ReasoningItem(
            type="reasoning",
            id=item_id,
            content=[ReasoningContent(text=part.content)],
            status="in_progress",
        )
        output_index = self._append_output(item)
        self.in_flight.current_reasoning = item
        return [
            ResponseOutputItemAddedEvent(
                response_id=self.response.id,
                item=item,
                output_index=output_index,
            )
        ]

    def _on_thinking_delta(self, delta: ThinkingPartDelta) -> list[ResponseStreamEvent]:
        """Append thinking text to the current reasoning item."""
        if delta.content_delta is None:
            return []
        item = self.in_flight.current_reasoning
        if item is None:
            return []
        self.in_flight.extend_reasoning(delta.content_delta)
        return [
            ResponseReasoningTextDeltaEvent(
                content_index=0,
                delta=delta.content_delta,
                item_id=item.id,
                output_index=self._index(item),
            )
        ]

    def _on_thinking_end(
        self, _part: ThinkingPart, followed_by_thinking: bool
    ) -> list[ResponseStreamEvent]:
        """Close the current reasoning item when thinking is finished."""
        if followed_by_thinking:
            return []
        item = self.in_flight.current_reasoning
        if item is None:
            return []
        text_part = open_reasoning_text_part(item)
        text = text_part.text if text_part is not None else ""
        item.status = "completed"
        output_index = self._index(item)
        self.in_flight.current_reasoning = None
        return [
            ResponseReasoningTextDoneEvent(
                content_index=0,
                text=text,
                item_id=item.id,
                output_index=output_index,
            ),
            ResponseOutputItemDoneEvent(
                response_id=self.response.id,
                item=item,
                output_index=output_index,
            ),
        ]

    def _on_tool_call_start(self, part: ToolCallPart) -> list[ResponseStreamEvent]:
        """Open a typed or generic tool-call output item."""
        kind, server_label = classify_tool(
            part.tool_name,
            self.policy.mcp_tool_servers,
            self.policy.knowledge_tool_name,
        )
        arguments = arguments_json(part.args)
        item = self._build_tool_item(kind, part, arguments, server_label)
        output_index = self._append_output(item)
        self.in_flight.open_tools[part.tool_call_id] = item
        events: list[ResponseStreamEvent] = [
            ResponseOutputItemAddedEvent(
                response_id=self.response.id,
                item=item,
                output_index=output_index,
            )
        ]
        events.extend(self._tool_start_progress(item, output_index))
        if (
            isinstance(item, (FunctionToolCall, McpCall))
            and arguments
            and arguments != "{}"
        ):
            events.append(self._arguments_delta(item, arguments, output_index))
        return events

    def _on_tool_call_delta(
        self, delta: ToolCallPartDelta
    ) -> list[ResponseStreamEvent]:
        """Append argument deltas onto the matching open tool item."""
        tool_call_id = cast(str, delta.tool_call_id)
        item = self.in_flight.extend_tool(tool_call_id, delta.args_delta)
        if item is None or isinstance(item, FileSearchToolCall):
            return []
        chunk = arguments_delta_text(delta.args_delta)
        if not chunk:
            return []
        return [self._arguments_delta(item, chunk, self._index(item))]

    def _on_tool_call_end(self, part: ToolCallPart) -> list[ResponseStreamEvent]:
        """Emit arguments-done for the finished tool-call part."""
        item = self.in_flight.extend_tool(
            part.tool_call_id,
            part.args,
            replace=True,
        )
        if item is None or isinstance(item, FileSearchToolCall):
            return []
        return [self._arguments_done(item, self._index(item))]

    def _on_function_tool_call(
        self, event: FunctionToolCallEvent
    ) -> list[ResponseStreamEvent]:
        """Emit file-search searching once the in-loop call is dispatched."""
        item = self.in_flight.tool(event.part.tool_call_id)
        if item is None or not isinstance(item, FileSearchToolCall):
            return []
        return [
            ResponseFileSearchCallSearchingEvent(
                item_id=item.id,
                output_index=self._index(item),
            )
        ]

    def _on_function_tool_result(
        self, event: FunctionToolResultEvent
    ) -> list[ResponseStreamEvent]:
        """Complete an in-loop tool item from its return or retry prompt."""
        part = event.part
        item = self.in_flight.tool(part.tool_call_id)
        if item is None:
            return []
        failed = tool_failed(part)
        if isinstance(item, McpCall):
            return self._complete_mcp(part.tool_call_id, item, part, failed)
        if isinstance(item, FileSearchToolCall):
            return self._complete_file_search(part.tool_call_id, item, part, failed)
        return self._complete_function(part.tool_call_id, item, failed)

    def _on_deferred_tool_requests(
        self, event: DeferredToolRequestsEvent
    ) -> list[ResponseStreamEvent]:
        """Mark deferred client function calls completed for the client."""
        events: list[ResponseStreamEvent] = []
        for call in event.requests.calls:
            item = self.in_flight.tool(call.tool_call_id)
            if item is None or not isinstance(item, FunctionToolCall):
                continue
            events.extend(
                self._complete_function(call.tool_call_id, item, failed=False)
            )
        return events

    def _complete_function(
        self, tool_call_id: str, item: FunctionToolCall, failed: bool
    ) -> list[ResponseStreamEvent]:
        """Finish a generic function_call output item."""
        self.in_flight.close_tool(tool_call_id)
        item.status = "failed" if failed else "completed"
        return [
            ResponseOutputItemDoneEvent(
                response_id=self.response.id,
                item=item,
                output_index=self._index(item),
            )
        ]

    def _complete_mcp(
        self,
        tool_call_id: str,
        item: McpCall,
        part: ToolReturnPart | RetryPromptPart,
        failed: bool,
    ) -> list[ResponseStreamEvent]:
        """Finish an mcp_call item with output or error text."""
        self.in_flight.close_tool(tool_call_id)
        item.output = None if failed else return_text(part)
        item.error = return_text(part) if failed else None
        output_index = self._index(item)
        progress: ResponseStreamEvent
        if failed:
            progress = ResponseMcpCallFailedEvent(
                item_id=item.id,
                output_index=output_index,
            )
        else:
            progress = ResponseMcpCallCompletedEvent(
                item_id=item.id,
                output_index=output_index,
            )
        return [
            progress,
            ResponseOutputItemDoneEvent(
                response_id=self.response.id,
                item=item,
                output_index=output_index,
            ),
        ]

    def _complete_file_search(
        self,
        tool_call_id: str,
        item: FileSearchToolCall,
        part: ToolReturnPart | RetryPromptPart,
        failed: bool,
    ) -> list[ResponseStreamEvent]:
        """Finish a file_search_call item and attach knowledge results when present."""
        self.in_flight.close_tool(tool_call_id)
        results = None
        if not failed and isinstance(part, ToolReturnPart):
            rows = file_search_results_from_content(part.content)
            if self.policy.include_file_search_results:
                results = rows
        item.status = "failed" if failed else "completed"
        item.results = results
        output_index = self._index(item)
        return [
            ResponseFileSearchCallCompletedEvent(
                item_id=item.id,
                output_index=output_index,
            ),
            ResponseOutputItemDoneEvent(
                response_id=self.response.id,
                item=item,
                output_index=output_index,
            ),
        ]

    def _build_tool_item(
        self,
        kind: ProjectedToolKind,
        part: ToolCallPart,
        arguments: str,
        server_label: Optional[str],
    ) -> OpenTool:
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
        self, item: OpenTool, output_index: int
    ) -> list[ResponseStreamEvent]:
        """Emit in-progress events after output_item.added for a tool."""
        item_id = _tool_id(item)
        if isinstance(item, McpCall):
            return [
                ResponseMcpCallInProgressEvent(
                    item_id=item_id,
                    output_index=output_index,
                )
            ]
        if isinstance(item, FileSearchToolCall):
            return [
                ResponseFileSearchCallInProgressEvent(
                    item_id=item_id,
                    output_index=output_index,
                )
            ]
        return []

    def _arguments_delta(
        self, item: FunctionToolCall | McpCall, delta: str, output_index: int
    ) -> ResponseStreamEvent:
        """Build an arguments-delta event for function or MCP calls."""
        item_id = _tool_id(item)
        if isinstance(item, McpCall):
            return ResponseMcpCallArgumentsDeltaEvent(
                delta=delta,
                item_id=item_id,
                output_index=output_index,
            )
        return ResponseFunctionCallArgumentsDeltaEvent(
            delta=delta,
            item_id=item_id,
            output_index=output_index,
        )

    def _arguments_done(
        self, item: FunctionToolCall | McpCall, output_index: int
    ) -> ResponseStreamEvent:
        """Build an arguments-done event for function or MCP calls."""
        item_id = _tool_id(item)
        if isinstance(item, McpCall):
            return ResponseMcpCallArgumentsDoneEvent(
                arguments=item.arguments,
                item_id=item_id,
                output_index=output_index,
            )
        return ResponseFunctionCallArgumentsDoneEvent(
            arguments=item.arguments,
            item_id=item_id,
            output_index=output_index,
        )

    def _append_output(self, item: ResponseOutput) -> int:
        """Append an item to the live envelope and return its output index."""
        output_index = len(self.response.output)
        self.response.output.append(item)
        if self.policy.filter_server_tools and is_server_managed_output_item(
            item, self.policy.configured_mcp_labels, self.policy.client_tool_types
        ):
            self.in_flight.hidden_output_indices.add(output_index)
        return output_index

    def _index(self, item: ResponseOutput) -> int:
        """Return the live output index of an item already in the envelope."""
        return self.response.output.index(item)

    def _open_refusal(self, text: str) -> list[ResponseStreamEvent]:
        """Register a completed refusal message and return its stream events."""
        item_id = f"msg_{self.response.id}_{len(self.response.output)}"
        item = refusal_message(item_id, text, "completed")
        output_index = self._append_output(item)
        return refusal_stream_events(
            response_id=self.response.id,
            item=item,
            output_index=output_index,
            text=text,
        )

    def _has_assistant_message(self) -> bool:
        """Return whether any assistant message is already in output."""
        return any(isinstance(item, ResponseMessage) for item in self._client_output())

    def _terminal_events(self, status: _ResponseStatus) -> list[ResponseStreamEvent]:
        """Build the lifecycle event that closes the response."""
        snapshot = self._snapshot()
        if status == "failed":
            return [ResponseFailedEvent(response=snapshot)]
        if status == "incomplete":
            return [ResponseIncompleteEvent(response=snapshot)]
        return [ResponseCompletedEvent(response=snapshot)]

    def _complete_from_result(
        self,
        result: AgentRunResult[Any],
        *,
        status: _ResponseStatus = "completed",
        error: Optional[ResponseError] = None,
    ) -> None:
        """Apply run usage and mark the response terminal."""
        self.response.usage = usage_from_run(result.usage)
        self._mark_terminal(status, error=error)

    def _client_output(self) -> list[ResponseOutput]:
        """Output items visible to the client after server-tool filtering."""
        if not self.policy.filter_server_tools:
            return list(self.response.output)
        return [
            item
            for index, item in enumerate(self.response.output)
            if index not in self.in_flight.hidden_output_indices
        ]

    def _output_text(self) -> str:
        """Build the response.output_text string from visible assistant messages."""
        chunks: list[str] = []
        for item in self._client_output():
            if not isinstance(item, ResponseMessage):
                continue
            for part in cast(Sequence[OutputMessageContent], item.content):
                if isinstance(part, OutputTextPart):
                    chunks.append(part.text)
                else:
                    chunks.append(part.refusal)
        return "".join(chunks)

    def _mark_terminal(
        self,
        status: _ResponseStatus,
        error: Optional[ResponseError] = None,
    ) -> None:
        """Write terminal fields onto the live envelope before snapshot."""
        self.response.status = status
        self.response.completed_at = int(time.time())
        if error is not None:
            self.response.error = error
        self.response.available_quotas = dict(self.policy.available_quotas)
        self.response.output_text = self._output_text()

    def _snapshot(self) -> ResponseObject:
        """Return a deep copy of the live envelope for lifecycle events.

        The live output list keeps server-managed items so in-loop tools can
        finish; the client copy omits hidden tool indices when filtering is on.
        """
        snap = self.response.model_copy(deep=True)
        if self.policy.filter_server_tools:
            snap.output = [
                item
                for index, item in enumerate(snap.output)
                if index not in self.in_flight.hidden_output_indices
            ]
        return snap

    def _emit(
        self, events: Iterable[ResponseStreamEvent]
    ) -> Iterator[ResponseStreamEvent]:
        """Assign sequence numbers and drop filtered server-tool events."""
        for event in events:
            if should_filter_stream_event(
                event,
                self.policy.filter_server_tools,
                self.in_flight.hidden_output_indices,
            ):
                continue
            yield self._with_sequence(event)

    def _with_sequence(self, event: ResponseStreamEvent) -> ResponseStreamEvent:
        """Assign the next client-visible sequence number to an event."""
        return event.model_copy(update={"sequence_number": self._take_seq()})

    def _take_seq(self) -> int:
        """Return the next event sequence number."""
        number = self._sequence
        self._sequence += 1
        return number


def _tool_id(item: OpenTool) -> str:
    """Return the OpenResponses item id for an in-flight tool."""
    return item.call_id if isinstance(item, FunctionToolCall) else item.id
