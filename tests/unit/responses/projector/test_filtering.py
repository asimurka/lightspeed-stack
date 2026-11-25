"""Tests for Responses projector client/server filtering."""

from responses.models.events import (
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseMcpCallInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputTextDeltaEvent,
)
from responses.models.items import FunctionToolCall, McpCall
from responses.projector.filtering import (
    is_server_managed_output_item,
    should_filter_stream_event,
)


def _mcp_call(server_label: str = "jira") -> McpCall:
    """Build a minimal MCP output item."""
    return McpCall(
        id="mcp_1",
        arguments="{}",
        name="create_issue",
        server_label=server_label,
    )


class TestIsServerManagedOutputItem:
    """Server-deployed MCP and file search are identified for filtering."""

    def test_configured_mcp_is_server_managed(self) -> None:
        """MCP items whose label is in config are server-managed."""
        assert is_server_managed_output_item(
            _mcp_call("jira"),
            configured_mcp_labels={"jira"},
            client_tool_types=set(),
        )

    def test_client_mcp_is_not_server_managed(self) -> None:
        """MCP items from a client-only label stay visible."""
        assert not is_server_managed_output_item(
            _mcp_call("local"),
            configured_mcp_labels={"jira"},
            client_tool_types={"mcp"},
        )

    def test_function_call_is_never_server_managed(self) -> None:
        """Client function calls are never treated as server tools."""
        item = FunctionToolCall(
            call_id="c1", name="get_weather", arguments="{}", id="c1"
        )
        assert not is_server_managed_output_item(
            item,
            configured_mcp_labels={"jira"},
            client_tool_types=set(),
        )


class TestShouldFilterStreamEvent:
    """Only server-tool item streams are dropped when filtering is on."""

    def test_disabled_filtering_keeps_mcp_events(self) -> None:
        """Filtering off yields every projected event."""
        event = ResponseMcpCallInProgressEvent(
            item_id="mcp_1", output_index=0, sequence_number=0
        )
        assert not should_filter_stream_event(event, False, {0})

    def test_filters_hidden_mcp_progress(self) -> None:
        """MCP progress events at a hidden index are dropped."""
        event = ResponseMcpCallInProgressEvent(
            item_id="mcp_1", output_index=2, sequence_number=0
        )
        assert should_filter_stream_event(event, True, {2})

    def test_keeps_text_deltas(self) -> None:
        """Text deltas are never server-tool events."""
        event = ResponseOutputTextDeltaEvent(
            content_index=0,
            delta="hi",
            item_id="msg_1",
            output_index=0,
            sequence_number=0,
        )
        assert not should_filter_stream_event(event, True, {1})

    def test_keeps_function_argument_deltas(self) -> None:
        """Deferred function argument events stay on the client stream."""
        event = ResponseFunctionCallArgumentsDeltaEvent(
            delta="{", item_id="c1", output_index=0, sequence_number=0
        )
        assert not should_filter_stream_event(event, True, set())

    def test_filters_hidden_item_added(self) -> None:
        """output_item.added for a hidden index is dropped."""
        event = ResponseOutputItemAddedEvent(
            response_id="resp_1",
            item=_mcp_call(),
            output_index=1,
            sequence_number=0,
        )
        assert should_filter_stream_event(event, True, {1})
