"""Hide server-managed tool output from client-visible OpenResponses streams."""

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
    """Return whether an output item is from a server-deployed tool.

    Args:
        item: Projected output item.
        configured_mcp_labels: MCP server labels owned by the service config.
        client_tool_types: Tool types the client registered on the request.

    Returns:
        True if the item should be hidden when server-tool filtering is on.

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
    """Return whether an event must not be sent to the client.

    Args:
        event: Projected stream event.
        filter_server_tools: Whether server-tool hiding is enabled.
        hidden_output_indices: Output indices marked as server-managed.

    Returns:
        True if the event should be dropped from the client stream.

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
