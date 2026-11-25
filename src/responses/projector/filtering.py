"""Client/server OpenResponses output filtering for the Responses projector."""

from collections.abc import Set as AbstractSet

from responses.models.events import (
    ResponseFileSearchCallCompletedEvent,
    ResponseFileSearchCallInProgressEvent,
    ResponseFileSearchCallSearchingEvent,
    ResponseMcpCallArgumentsDeltaEvent,
    ResponseMcpCallArgumentsDoneEvent,
    ResponseMcpCallCompletedEvent,
    ResponseMcpCallFailedEvent,
    ResponseMcpCallInProgressEvent,
    ResponseMcpListToolsCompletedEvent,
    ResponseMcpListToolsFailedEvent,
    ResponseMcpListToolsInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseStreamEvent,
)
from responses.models.items import (
    FileSearchToolCall,
    McpApprovalRequest,
    McpCall,
    McpListTools,
    ResponseOutput,
)


def is_server_managed_output_item(
    item: ResponseOutput,
    configured_mcp_labels: AbstractSet[str],
    client_tool_types: AbstractSet[str],
) -> bool:
    """Return whether an output item belongs to a server-deployed tool.

    Args:
        item: Projected OpenResponses output item.
        configured_mcp_labels: MCP server labels from LCORE configuration.
        client_tool_types: Tool types supplied on the client request.

    Returns:
        True when the item should be hidden from the client if server-tool
        filtering is enabled.

    """
    if isinstance(item, (McpCall, McpListTools, McpApprovalRequest)):
        return item.server_label in configured_mcp_labels
    return (
        isinstance(item, FileSearchToolCall) and "file_search" not in client_tool_types
    )


def should_filter_stream_event(
    event: ResponseStreamEvent,
    filter_server_tools: bool,
    hidden_output_indices: AbstractSet[int],
) -> bool:
    """Return whether a projected event must be omitted from the client stream.

    Args:
        event: OpenResponses event produced by the projector.
        filter_server_tools: Whether server-deployed tool output is hidden.
        hidden_output_indices: Output indices of hidden server tool items.

    Returns:
        True when the event must not be yielded to the client.

    """
    if not filter_server_tools:
        return False

    if isinstance(event, (ResponseOutputItemAddedEvent, ResponseOutputItemDoneEvent)):
        return event.output_index in hidden_output_indices

    if isinstance(
        event,
        (
            ResponseMcpCallInProgressEvent,
            ResponseMcpCallFailedEvent,
            ResponseMcpCallCompletedEvent,
            ResponseMcpCallArgumentsDeltaEvent,
            ResponseMcpCallArgumentsDoneEvent,
            ResponseMcpListToolsInProgressEvent,
            ResponseMcpListToolsFailedEvent,
            ResponseMcpListToolsCompletedEvent,
            ResponseFileSearchCallInProgressEvent,
            ResponseFileSearchCallSearchingEvent,
            ResponseFileSearchCallCompletedEvent,
        ),
    ):
        return event.output_index in hidden_output_indices

    return False
