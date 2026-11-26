"""Per-run settings for OpenResponses event projection."""

from dataclasses import dataclass, field

from responses.projector.classify import KNOWLEDGE_TOOL_NAME


@dataclass(frozen=True)
class ProjectionPolicy:
    """Tool classification, client visibility, and quota echo for one run.

    Quotas are applied on the response envelope only when the run ends.
    """

    filter_server_tools: bool = False
    configured_mcp_labels: frozenset[str] = field(default_factory=frozenset)
    client_tool_types: frozenset[str] = field(default_factory=frozenset)
    mcp_tool_servers: dict[str, str] = field(default_factory=dict)
    knowledge_tool_name: str = KNOWLEDGE_TOOL_NAME
    include_file_search_results: bool = True
    available_quotas: dict[str, int] = field(default_factory=dict)
