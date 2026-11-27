"""Per-run settings for OpenResponses event projection."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProjectionPolicy:
    """Per-run inputs that steer OpenResponses projection.

    Attributes:
        filter_server_tools: When True, hide server-deployed MCP and file-search
            output from the client stream and completed snapshots.
        configured_mcp_labels: MCP server labels owned by service configuration.
        client_tool_types: Tool types the client registered on the request.
        include_file_search_results: When False, file_search_call completes without
            embedding result rows on the item.
        available_quotas: Quota snapshot echoed on the response when the run ends.

    """

    filter_server_tools: bool = False
    configured_mcp_labels: frozenset[str] = field(default_factory=frozenset)
    client_tool_types: frozenset[str] = field(default_factory=frozenset)
    include_file_search_results: bool = True
    available_quotas: dict[str, int] = field(default_factory=dict)
