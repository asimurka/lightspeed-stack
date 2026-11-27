"""Tests for OpenResponsesEventStream PAI → OpenResponses projection."""

# pylint: disable=too-few-public-methods

from collections.abc import AsyncIterator, Sequence
from typing import Any

from pydantic_ai.messages import (
    DeferredToolRequestsEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.ui import NativeEvent

from knowledge.types import KnowledgeMatch
from responses.models.content import OutputTextPart
from responses.models.events import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseFileSearchCallCompletedEvent,
    ResponseFileSearchCallInProgressEvent,
    ResponseFileSearchCallSearchingEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseIncompleteEvent,
    ResponseMcpCallArgumentsDeltaEvent,
    ResponseMcpCallArgumentsDoneEvent,
    ResponseMcpCallCompletedEvent,
    ResponseMcpCallInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputTextDeltaEvent,
    ResponseOutputTextDoneEvent,
    ResponseRefusalDoneEvent,
    ResponseStreamEvent,
)
from responses.models.items import FileSearchToolCall, FunctionToolCall, McpCall
from responses.models.response import ResponseObject
from responses.projector import OpenResponsesEventStream, ProjectionPolicy
from responses.projector.refusal import DEFAULT_REFUSAL_TEXT

_POLICY_FIELDS = frozenset(
    {
        "filter_server_tools",
        "configured_mcp_labels",
        "client_tool_types",
        "include_file_search_results",
        "available_quotas",
    }
)


def _stream(**kwargs: Any) -> OpenResponsesEventStream:
    """Build a projector with stable identity fields for assertions."""
    policy_kwargs = {key: kwargs.pop(key) for key in _POLICY_FIELDS if key in kwargs}
    quotas = policy_kwargs.pop("available_quotas", {"user": 100})
    return OpenResponsesEventStream(
        response=ResponseObject(
            id=kwargs.pop("response_id", "resp_test"),
            model=kwargs.pop("model", "openai/test"),
            created_at=kwargs.pop("created_at", 1700000000),
            conversation=kwargs.pop("conversation", "conv_test"),
            status="in_progress",
            output=[],
            available_quotas={},
            output_text="",
            **kwargs,
        ),
        policy=ProjectionPolicy(available_quotas=quotas, **policy_kwargs),
    )


async def _native(*events: NativeEvent) -> AsyncIterator[NativeEvent]:
    """Yield synthetic PAI events in order."""
    for event in events:
        yield event


async def _project(
    events: Sequence[NativeEvent],
    projector: OpenResponsesEventStream | None = None,
) -> tuple[OpenResponsesEventStream, list[ResponseStreamEvent]]:
    """Run transform_stream over synthetic PAI events."""
    stream = projector or _stream()
    projected: list[ResponseStreamEvent] = []
    async for event in stream.transform_stream(_native(*events)):
        projected.append(event)
    return stream, projected


def _run_result(output: Any = "done") -> AgentRunResultEvent:
    """Terminal PAI run-result event."""
    return AgentRunResultEvent(result=AgentRunResult(output=output))


def _run_result_with_finish(
    *,
    finish_reason: str,
    output: str = "",
    provider_details: dict[str, str] | None = None,
) -> AgentRunResultEvent:
    """Terminal run-result event with a model finish reason."""
    run = AgentRunResult(output=output or finish_reason)
    run._state.message_history = [  # pylint: disable=protected-access
        ModelResponse(
            parts=[TextPart(content=output)] if output else [],
            finish_reason=finish_reason,  # type: ignore[arg-type]
            provider_details=provider_details,
        )
    ]
    return AgentRunResultEvent(result=run)


def _event_types(events: Sequence[ResponseStreamEvent]) -> list[str]:
    """Return projected event type strings."""
    return [event.type for event in events]


class TestLifecycle:
    """Stream start and run completion become response lifecycle events."""

    async def test_created_then_in_progress_then_completed(self) -> None:
        """An empty run still emits created, in_progress, and completed."""
        _, events = await _project([_run_result()])
        assert _event_types(events) == [
            "response.created",
            "response.in_progress",
            "response.completed",
        ]
        assert isinstance(events[0], ResponseCreatedEvent)
        assert events[0].response.status == "in_progress"
        assert events[0].response.output_text == ""
        assert events[0].response.available_quotas == {}
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.status == "completed"
        assert completed.response.available_quotas == {"user": 100}
        assert completed.sequence_number == 2

    async def test_consume_matches_completed_response(self) -> None:
        """Buffered JSON is the completed event's response, not a second mapper."""
        projector = _stream()
        _, events = await _project([_run_result("hello")], projector)
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert projector.final_response.model_dump() == completed.response.model_dump()

    async def test_on_error_emits_failed(self) -> None:
        """Mid-run errors become response.failed."""

        async def broken() -> AsyncIterator[NativeEvent]:
            yield PartStartEvent(index=0, part=TextPart(content="hi"))
            raise RuntimeError("provider down")

        projector = _stream()
        events = [event async for event in projector.transform_stream(broken())]
        assert events[-1].type == "response.failed"
        failed = events[-1]
        assert isinstance(failed, ResponseFailedEvent)
        assert failed.response.status == "failed"
        assert failed.response.error is not None
        assert "provider down" in failed.response.error.message


class TestTextProjection:
    """Text parts become message items and output_text events."""

    async def test_text_start_delta_end(self) -> None:
        """A streamed text part opens, deltas, then closes a message item."""
        _, events = await _project(
            [
                PartStartEvent(index=0, part=TextPart(content="Hel")),
                PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="lo")),
                PartEndEvent(index=0, part=TextPart(content="Hello")),
                _run_result("Hello"),
            ]
        )
        types = _event_types(events)
        assert types[0:2] == ["response.created", "response.in_progress"]
        assert "response.output_item.added" in types
        assert "response.content_part.added" in types
        assert "response.output_text.delta" in types
        assert "response.output_text.done" in types
        assert "response.output_item.done" in types
        deltas = [
            event for event in events if isinstance(event, ResponseOutputTextDeltaEvent)
        ]
        assert [event.delta for event in deltas] == ["Hel", "lo"]
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output_text == "Hello"
        assert completed.response.output[0].type == "message"

    async def test_consecutive_text_parts_keep_accumulated_text(self) -> None:
        """Merged text parts must not be overwritten by the last part's content."""
        _, events = await _project(
            [
                PartStartEvent(index=0, part=TextPart(content="Hello")),
                PartEndEvent(
                    index=0,
                    part=TextPart(content="Hello"),
                    next_part_kind="text",
                ),
                PartStartEvent(
                    index=1,
                    part=TextPart(content=" world"),
                    previous_part_kind="text",
                ),
                PartEndEvent(index=1, part=TextPart(content=" world")),
                _run_result("Hello world"),
            ]
        )
        done = [
            event for event in events if isinstance(event, ResponseOutputTextDoneEvent)
        ]
        assert len(done) == 1
        assert done[0].text == "Hello world"
        assert (
            "".join(
                event.delta
                for event in events
                if isinstance(event, ResponseOutputTextDeltaEvent)
            )
            == "Hello world"
        )
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output_text == "Hello world"


class TestDeferredFunctionTools:
    """Deferred client tools stay function_call items."""

    async def test_deferred_call_is_function_call(self) -> None:
        """External tools project as function_call, not mcp_call."""
        part = ToolCallPart(
            tool_name="get_weather",
            args={"city": "Boston"},
            tool_call_id="call_weather",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                DeferredToolRequestsEvent(requests=DeferredToolRequests(calls=[part])),
                _run_result(DeferredToolRequests(calls=[part])),
            ]
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, FunctionToolCall)
        assert added[0].item.name == "get_weather"
        assert added[0].item.call_id == "call_weather"
        assert any(
            isinstance(event, ResponseFunctionCallArgumentsDoneEvent)
            for event in events
        )
        assert not any(event.type.startswith("response.mcp_call") for event in events)
        done = [
            event for event in events if isinstance(event, ResponseOutputItemDoneEvent)
        ]
        assert done[-1].item.type == "function_call"


class TestInLoopFunctionTools:
    """Unrelated in-loop function tools stay generic function_call items."""

    async def test_generic_in_loop_function(self) -> None:
        """Skills-style in-loop tools are not rewritten as MCP or file search."""
        part = ToolCallPart(
            tool_name="load_skill",
            args={"name": "git"},
            tool_call_id="call_skill",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(args_delta="", tool_call_id="call_skill"),
                ),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="load_skill",
                        content="ok",
                        tool_call_id="call_skill",
                    )
                ),
                _run_result("ok"),
            ]
        )
        added = [
            event.item
            for event in events
            if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0], FunctionToolCall)
        assert added[0].name == "load_skill"
        assert not any(
            event.type.startswith("response.mcp_call")
            or event.type.startswith("response.file_search_call")
            for event in events
        )

    async def test_string_argument_deltas_append(self) -> None:
        """String tool-call deltas concatenate onto function_call.arguments."""
        start = ToolCallPart(
            tool_name="load_skill",
            args="",
            tool_call_id="call_skill",
        )
        end = ToolCallPart(
            tool_name="load_skill",
            args={"name": "git"},
            tool_call_id="call_skill",
        )
        projector, events = await _project(
            [
                PartStartEvent(index=0, part=start),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(
                        args_delta='{"name":',
                        tool_call_id="call_skill",
                    ),
                ),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(
                        args_delta=' "git"}',
                        tool_call_id="call_skill",
                    ),
                ),
                PartEndEvent(index=0, part=end),
                FunctionToolCallEvent(end),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="load_skill",
                        content="ok",
                        tool_call_id="call_skill",
                    )
                ),
                _run_result("ok"),
            ]
        )
        item = next(
            output
            for output in projector.response.output
            if isinstance(output, FunctionToolCall)
        )
        assert item.arguments == '{"name": "git"}'
        streamed = "".join(
            event.delta
            for event in events
            if isinstance(event, ResponseFunctionCallArgumentsDeltaEvent)
        )
        assert streamed == item.arguments

    async def test_argument_deltas_without_tool_call_id_use_last_opened(self) -> None:
        """Deltas that omit tool_call_id attach to the last opened tool."""
        start = ToolCallPart(
            tool_name="load_skill",
            args="",
            tool_call_id="call_skill",
        )
        end = ToolCallPart(
            tool_name="load_skill",
            args={"name": "git"},
            tool_call_id="call_skill",
        )
        projector, events = await _project(
            [
                PartStartEvent(index=0, part=start),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(args_delta='{"name":'),
                ),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(args_delta=' "git"}'),
                ),
                PartEndEvent(index=0, part=end),
                FunctionToolCallEvent(end),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="load_skill",
                        content="ok",
                        tool_call_id="call_skill",
                    )
                ),
                _run_result("ok"),
            ]
        )
        item = next(
            output
            for output in projector.response.output
            if isinstance(output, FunctionToolCall)
        )
        assert item.arguments == '{"name": "git"}'
        streamed = "".join(
            event.delta
            for event in events
            if isinstance(event, ResponseFunctionCallArgumentsDeltaEvent)
        )
        assert streamed == item.arguments

    async def test_dict_argument_deltas_shallow_merge(self) -> None:
        """Dict tool-call deltas merge into function_call.arguments."""
        start = ToolCallPart(
            tool_name="load_skill",
            args={},
            tool_call_id="call_skill",
        )
        end = ToolCallPart(
            tool_name="load_skill",
            args={"name": "git", "version": "2"},
            tool_call_id="call_skill",
        )
        projector, events = await _project(
            [
                PartStartEvent(index=0, part=start),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(
                        args_delta={"name": "git"},
                        tool_call_id="call_skill",
                    ),
                ),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(
                        args_delta={"version": "2"},
                        tool_call_id="call_skill",
                    ),
                ),
                PartEndEvent(index=0, part=end),
                FunctionToolCallEvent(end),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="load_skill",
                        content="ok",
                        tool_call_id="call_skill",
                    )
                ),
                _run_result("ok"),
            ]
        )
        item = next(
            output
            for output in projector.response.output
            if isinstance(output, FunctionToolCall)
        )
        assert item.arguments == '{"name": "git", "version": "2"}'
        deltas = [
            event.delta
            for event in events
            if isinstance(event, ResponseFunctionCallArgumentsDeltaEvent)
        ]
        assert deltas == ['{"name": "git"', ', "version": "2"', "}"]
        assert "".join(deltas) == item.arguments
        done = next(
            event
            for event in events
            if isinstance(event, ResponseFunctionCallArgumentsDoneEvent)
        )
        assert done.arguments == item.arguments


class TestMcpProjection:
    """In-loop MCP function tools become typed mcp_call items."""

    async def test_mcp_call_and_result(self) -> None:
        """A prefixed MCP tool emits mcp_call lifecycle events and output."""
        part = ToolCallPart(
            tool_name="mcp:jira:_create_issue",
            args={"title": "bug"},
            tool_call_id="call_mcp",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:jira:_create_issue",
                        content="ISSUE-1",
                        tool_call_id="call_mcp",
                    )
                ),
                _run_result("created"),
            ],
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, McpCall)
        assert added[0].item.server_label == "jira"
        assert added[0].item.name == "create_issue"
        assert any(
            isinstance(event, ResponseMcpCallInProgressEvent) for event in events
        )
        assert any(
            isinstance(event, ResponseMcpCallArgumentsDoneEvent) for event in events
        )
        assert any(isinstance(event, ResponseMcpCallCompletedEvent) for event in events)
        done = [
            event for event in events if isinstance(event, ResponseOutputItemDoneEvent)
        ]
        assert isinstance(done[-1].item, McpCall)
        assert done[-1].item.output == "ISSUE-1"
        assert not any(
            isinstance(event.item, FunctionToolCall)
            for event in events
            if isinstance(event, ResponseOutputItemAddedEvent)
        )

    async def test_mcp_toolset_prefix_is_mcp_call(self) -> None:
        """PAI MCP toolset names project as mcp_call, not mcp_list_tools."""
        part = ToolCallPart(
            tool_name="mcp:docs:_lookup_topic",
            args={"q": "pods"},
            tool_call_id="call_mcp",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:docs:_lookup_topic",
                        content="ok",
                        tool_call_id="call_mcp",
                    )
                ),
                _run_result("ok"),
            ]
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, McpCall)
        assert added[0].item.name == "lookup_topic"
        assert added[0].item.server_label == "docs"
        assert not any(
            event.type.startswith("response.mcp_list_tools") for event in events
        )

    async def test_underscore_in_label_and_bare_name(self) -> None:
        """PAI mcp:{label}:_ split keeps underscores inside each field."""
        part = ToolCallPart(
            tool_name="mcp:my_jira:_run_query_v2",
            args={"q": "pods"},
            tool_call_id="call_mcp",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:my_jira:_run_query_v2",
                        content="ok",
                        tool_call_id="call_mcp",
                    )
                ),
                _run_result("ok"),
            ]
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, McpCall)
        assert added[0].item.server_label == "my_jira"
        assert added[0].item.name == "run_query_v2"

    async def test_legacy_mcp_underscore_prefix_is_function_call(self) -> None:
        """Names without mcp:{label}:_ stay generic function tools."""
        part = ToolCallPart(
            tool_name="mcp_create_issue",
            args={"title": "bug"},
            tool_call_id="call_legacy",
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp_create_issue",
                        content="ok",
                        tool_call_id="call_legacy",
                    )
                ),
                _run_result("ok"),
            ]
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, FunctionToolCall)
        assert added[0].item.name == "mcp_create_issue"
        assert not any(event.type.startswith("response.mcp_call") for event in events)

    async def test_full_mcp_turn_event_sequence(self) -> None:
        """A realistic PAI MCP turn projects the OpenResponses event order.

        Model thinking, a streamed mcp:jira:_create_issue call, the in-loop
        result, then the assistant reply.
        """
        thinking = ThinkingPart(content="I'll file this in Jira.")
        tool_start = ToolCallPart(
            tool_name="mcp:jira:_create_issue",
            args="",
            tool_call_id="call_jira_1",
        )
        tool_end = ToolCallPart(
            tool_name="mcp:jira:_create_issue",
            args={"title": "login fails"},
            tool_call_id="call_jira_1",
        )
        reply_start = TextPart(content="Created ")
        reply_end = TextPart(content="Created PROJ-1")
        projector, events = await _project(
            [
                PartStartEvent(index=0, part=thinking),
                PartEndEvent(
                    index=0,
                    part=thinking,
                    next_part_kind="tool-call",
                ),
                PartStartEvent(
                    index=1,
                    part=tool_start,
                    previous_part_kind="thinking",
                ),
                PartDeltaEvent(
                    index=1,
                    delta=ToolCallPartDelta(
                        args_delta='{"title":',
                        tool_call_id="call_jira_1",
                    ),
                ),
                PartDeltaEvent(
                    index=1,
                    delta=ToolCallPartDelta(
                        args_delta=' "login fails"}',
                        tool_call_id="call_jira_1",
                    ),
                ),
                PartEndEvent(index=1, part=tool_end),
                FunctionToolCallEvent(tool_end),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:jira:_create_issue",
                        content='{"key":"PROJ-1"}',
                        tool_call_id="call_jira_1",
                    )
                ),
                PartStartEvent(index=0, part=reply_start),
                PartDeltaEvent(
                    index=0,
                    delta=TextPartDelta(content_delta="PROJ-1"),
                ),
                PartEndEvent(index=0, part=reply_end),
                _run_result("Created PROJ-1"),
            ]
        )

        assert _event_types(events) == [
            "response.created",
            "response.in_progress",
            "response.output_item.added",
            "response.reasoning_text.delta",
            "response.reasoning_text.done",
            "response.output_item.done",
            "response.output_item.added",
            "response.mcp_call.in_progress",
            "response.mcp_call_arguments.delta",
            "response.mcp_call_arguments.delta",
            "response.mcp_call_arguments.done",
            "response.mcp_call.completed",
            "response.output_item.done",
            "response.output_item.added",
            "response.content_part.added",
            "response.output_text.delta",
            "response.output_text.delta",
            "response.output_text.done",
            "response.content_part.done",
            "response.output_item.done",
            "response.completed",
        ]
        assert [event.sequence_number for event in events] == list(range(len(events)))

        mcp_added = events[6]
        assert isinstance(mcp_added, ResponseOutputItemAddedEvent)
        assert isinstance(mcp_added.item, McpCall)
        assert mcp_added.item.id == "call_jira_1"
        assert mcp_added.item.server_label == "jira"
        assert mcp_added.item.name == "create_issue"
        assert mcp_added.output_index == 1

        assert isinstance(events[7], ResponseMcpCallInProgressEvent)
        assert events[7].item_id == "call_jira_1"
        assert events[7].output_index == 1

        arg_deltas = [
            event
            for event in events
            if isinstance(event, ResponseMcpCallArgumentsDeltaEvent)
        ]
        assert [event.delta for event in arg_deltas] == [
            '{"title":',
            ' "login fails"}',
        ]
        assert "".join(event.delta for event in arg_deltas) == '{"title": "login fails"}'

        args_done = events[10]
        assert isinstance(args_done, ResponseMcpCallArgumentsDoneEvent)
        assert args_done.arguments == '{"title": "login fails"}'
        assert args_done.item_id == "call_jira_1"

        mcp_done = events[12]
        assert isinstance(mcp_done, ResponseOutputItemDoneEvent)
        assert mcp_done.item is mcp_added.item
        assert isinstance(mcp_done.item, McpCall)
        assert mcp_done.item.output == '{"key":"PROJ-1"}'
        assert mcp_done.item.error is None
        assert mcp_done.item.arguments == '{"title": "login fails"}'

        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert [item.type for item in completed.response.output] == [
            "reasoning",
            "mcp_call",
            "message",
        ]
        mcp_item = completed.response.output[1]
        assert isinstance(mcp_item, McpCall)
        assert mcp_item.arguments == '{"title": "login fails"}'
        assert mcp_item.output == '{"key":"PROJ-1"}'
        assert completed.response.output_text == "Created PROJ-1"
        assert projector.final_response.model_dump() == completed.response.model_dump()


class TestFileSearchProjection:
    """Knowledge / file-search tools become file_search_call items with RAG rows."""

    async def test_search_knowledge_with_results(self) -> None:
        """search_knowledge returns typed file_search_call results."""
        part = ToolCallPart(
            tool_name="search_knowledge",
            args={"query": "what is a pod"},
            tool_call_id="call_rag",
        )
        match = KnowledgeMatch(
            content="A pod is the smallest deployable unit.",
            score=0.91,
            id="chunk-1",
            source="https://docs.example/pod",
            metadata={"title": "Pods", "knowledge_source": "ocp-docs"},
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="search_knowledge",
                        content=[match],
                        tool_call_id="call_rag",
                    )
                ),
                _run_result("A pod is ..."),
            ]
        )
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, FileSearchToolCall)
        assert list(added[0].item.queries) == ["what is a pod"]
        assert any(
            isinstance(event, ResponseFileSearchCallInProgressEvent) for event in events
        )
        assert any(
            isinstance(event, ResponseFileSearchCallSearchingEvent) for event in events
        )
        assert any(
            isinstance(event, ResponseFileSearchCallCompletedEvent) for event in events
        )
        done = [
            event for event in events if isinstance(event, ResponseOutputItemDoneEvent)
        ]
        item = done[-1].item
        assert isinstance(item, FileSearchToolCall)
        assert item.status == "completed"
        assert item.results is not None
        assert item.results[0].text == match.content
        assert item.results[0].score == match.score
        assert item.results[0].filename == "Pods"
        assert not any(
            isinstance(event.item, FunctionToolCall)
            for event in events
            if isinstance(event, ResponseOutputItemAddedEvent)
        )

    async def test_search_knowledge_queries_come_from_final_args(self) -> None:
        """File search ignores argument deltas; queries come from the finished part."""
        start = ToolCallPart(
            tool_name="search_knowledge",
            args=None,
            tool_call_id="call_rag",
        )
        end = ToolCallPart(
            tool_name="search_knowledge",
            args={"query": "what is a pod"},
            tool_call_id="call_rag",
        )
        projector, events = await _project(
            [
                PartStartEvent(index=0, part=start),
                PartDeltaEvent(
                    index=0,
                    delta=ToolCallPartDelta(
                        args_delta='{"query": "',
                        tool_call_id="call_rag",
                    ),
                ),
                PartEndEvent(index=0, part=end),
                FunctionToolCallEvent(end),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="search_knowledge",
                        content=[],
                        tool_call_id="call_rag",
                    )
                ),
                _run_result("done"),
            ]
        )
        assert not any(
            event.type.startswith("response.function_call_arguments")
            or event.type.startswith("response.mcp_call_arguments")
            for event in events
        )
        item = next(
            output
            for output in projector.response.output
            if isinstance(output, FileSearchToolCall)
        )
        assert list(item.queries) == ["what is a pod"]

    async def test_search_then_text_has_no_output_annotations(self) -> None:
        """RAG hits stay on file_search_call; assistant text has no annotations."""
        part = ToolCallPart(
            tool_name="search_knowledge",
            args={"query": "pod"},
            tool_call_id="call_rag",
        )
        match = KnowledgeMatch(
            content="A pod is the smallest deployable unit.",
            score=0.91,
            id="chunk-1",
            source="https://docs.example/pod",
            metadata={"title": "Pods", "document_id": "doc-pod"},
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="search_knowledge",
                        content=[match],
                        tool_call_id="call_rag",
                    )
                ),
                PartStartEvent(index=1, part=TextPart(content="A pod is ...")),
                PartEndEvent(index=1, part=TextPart(content="A pod is ...")),
                _run_result("A pod is ..."),
            ]
        )
        assert all(
            event.type != "response.output_text.annotation.added" for event in events
        )
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        message = next(
            item for item in completed.response.output if item.type == "message"
        )
        assert isinstance(message.content, list)
        text_part = message.content[0]
        assert isinstance(text_part, OutputTextPart)
        assert text_part.annotations == []


class TestServerToolFiltering:
    """Client/server filtering is applied only in this projector."""

    async def test_hides_configured_mcp_from_client_stream(self) -> None:
        """Server MCP events are omitted when filter_server_tools is set."""
        part = ToolCallPart(
            tool_name="mcp:jira:_create_issue",
            args={"title": "bug"},
            tool_call_id="call_mcp",
        )
        projector = _stream(
            filter_server_tools=True,
            configured_mcp_labels=frozenset({"jira"}),
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:jira:_create_issue",
                        content="ISSUE-1",
                        tool_call_id="call_mcp",
                    )
                ),
                _run_result("ok"),
            ],
            projector,
        )
        assert not any(event.type.startswith("response.mcp_call") for event in events)
        assert not any(
            isinstance(event, ResponseOutputItemAddedEvent)
            and event.item.type == "mcp_call"
            for event in events
        )
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output == []

    async def test_client_mcp_stays_visible(self) -> None:
        """Request MCP that is not server-configured is still streamed."""
        part = ToolCallPart(
            tool_name="mcp:browser:_local_tool",
            args={},
            tool_call_id="call_local",
        )
        projector = _stream(
            filter_server_tools=True,
            configured_mcp_labels=frozenset({"jira"}),
            client_tool_types=frozenset({"mcp"}),
        )
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                FunctionToolCallEvent(part),
                FunctionToolResultEvent(
                    ToolReturnPart(
                        tool_name="mcp:browser:_local_tool",
                        content="ok",
                        tool_call_id="call_local",
                    )
                ),
                _run_result("ok"),
            ],
            projector,
        )
        assert any(isinstance(event, ResponseMcpCallCompletedEvent) for event in events)
        added = [
            event for event in events if isinstance(event, ResponseOutputItemAddedEvent)
        ]
        assert len(added) == 1
        assert isinstance(added[0].item, McpCall)
        assert added[0].item.server_label == "browser"
        assert added[0].item.name == "local_tool"


class TestRefusalAndTerminalRun:
    """Refusal and terminal run-result projection."""

    async def test_input_shield_short_circuit_streams_assistant_message(self) -> None:
        """Shield SkipModelRequest replay is PartStart plus PartEnd; start text is one delta."""
        rejection = "I can only answer questions about OpenShift."
        part = TextPart(rejection)
        _, events = await _project(
            [
                PartStartEvent(index=0, part=part),
                PartEndEvent(index=0, part=part),
                _run_result(rejection),
            ]
        )
        types = _event_types(events)
        assert types[0:2] == ["response.created", "response.in_progress"]
        assert "response.output_item.added" in types
        assert "response.output_text.delta" in types
        assert "response.output_text.done" in types
        assert "response.output_item.done" in types
        assert types[-1] == "response.completed"
        assert "response.refusal.delta" not in types
        text_deltas = [
            event
            for event in events
            if isinstance(event, ResponseOutputTextDeltaEvent)
        ]
        assert [event.delta for event in text_deltas] == [rejection]
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output_text == rejection
        message = completed.response.output[0]
        assert message.type == "message"
        assert isinstance(message.content, list)
        assert isinstance(message.content[0], OutputTextPart)
        assert message.content[0].text == rejection

    async def test_content_filter_emits_refusal_when_no_text(self) -> None:
        """A content-filter finish reason becomes a completed refusal."""
        _, events = await _project(
            [
                _run_result_with_finish(
                    finish_reason="content_filter",
                    provider_details={"refusal_response": "Policy blocked this."},
                )
            ]
        )
        assert any(isinstance(event, ResponseRefusalDoneEvent) for event in events)
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output_text == "Policy blocked this."

    async def test_content_filter_uses_default_refusal_text(self) -> None:
        """Content filter without provider text uses the default refusal."""
        _, events = await _project(
            [_run_result_with_finish(finish_reason="content_filter")]
        )
        completed = events[-1]
        assert isinstance(completed, ResponseCompletedEvent)
        assert completed.response.output_text == DEFAULT_REFUSAL_TEXT

    async def test_length_finish_reason_is_incomplete(self) -> None:
        """Max-length stops are incomplete, not failed."""
        _, events = await _project([_run_result_with_finish(finish_reason="length")])
        assert isinstance(events[-1], ResponseIncompleteEvent)
        assert events[-1].response.status == "incomplete"


class TestSseEncoding:
    """SSE encoding matches the existing /v1/responses wire format."""

    async def test_encode_event_uses_event_and_data_lines(self) -> None:
        """Each chunk has an event type line and JSON data."""
        projector = _stream()
        _, events = await _project([_run_result()], projector)
        encoded = projector.encode_event(events[0])
        assert encoded.startswith("event: response.created\n")
        assert encoded.startswith("event: response.created\ndata: {")
        assert encoded.endswith("\n\n")
        assert '"id": "resp_test"' in encoded
