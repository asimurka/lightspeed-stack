"""Map agent tool names to OpenResponses tool item kinds."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Optional

KNOWLEDGE_TOOL_NAME = "search_knowledge"
_MCP_NAME_PREFIX = "mcp_"


class ProjectedToolKind(StrEnum):
    """OpenResponses output item kind for an in-loop or deferred tool."""

    FUNCTION = "function"
    MCP = "mcp"
    FILE_SEARCH = "file_search"


def classify_tool(
    tool_name: str,
    mcp_tool_servers: Mapping[str, str],
    knowledge_tool_name: str = KNOWLEDGE_TOOL_NAME,
) -> tuple[ProjectedToolKind, Optional[str]]:
    """Classify an agent tool name for OpenResponses projection.

    MCP tools are expected to use the PAI mcp_ toolset prefix. Keys in
    mcp_tool_servers are the bare tool name (without mcp_).

    Args:
        tool_name: Tool name on the call or return.
        mcp_tool_servers: Bare MCP tool name to server label for this run.
        knowledge_tool_name: In-loop knowledge search tool name.

    Returns:
        Item kind and MCP server label when the tool is MCP.

    """
    if tool_name == knowledge_tool_name:
        return ProjectedToolKind.FILE_SEARCH, None

    if not (
        tool_name.startswith(_MCP_NAME_PREFIX)
        and len(tool_name) > len(_MCP_NAME_PREFIX)
    ):
        return ProjectedToolKind.FUNCTION, None

    bare = tool_name.removeprefix(_MCP_NAME_PREFIX)
    return ProjectedToolKind.MCP, mcp_tool_servers.get(bare) or "mcp"
