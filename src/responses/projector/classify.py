"""Classify in-loop PAI tools as MCP, file search, or generic functions."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Optional

KNOWLEDGE_TOOL_NAME = "search_knowledge"
_MCP_NAME_PREFIX = "mcp_"


class ProjectedToolKind(StrEnum):
    """How an in-loop or deferred tool is projected into OpenResponses items."""

    FUNCTION = "function"
    MCP = "mcp"
    FILE_SEARCH = "file_search"


def classify_tool(
    tool_name: str,
    mcp_tool_servers: Mapping[str, str],
    knowledge_tool_name: str = KNOWLEDGE_TOOL_NAME,
) -> tuple[ProjectedToolKind, Optional[str]]:
    """Return the OpenResponses tool kind and optional MCP server label.

    Agent-loop tools only. ``search_knowledge`` is file search. Names in
    ``mcp_tool_servers``, PrefixedToolset ``{label}_`` names, and the PAI MCP
    toolset ``mcp_`` prefix are MCP. Skills and every other in-loop name stay
    generic functions. There is no native-tool or ``mcp_list_tools`` path.

    Args:
        tool_name: PAI tool name on the call or return part.
        mcp_tool_servers: Map of MCP tool names to server labels for this run.
        knowledge_tool_name: LCORE knowledge / file-search function name.

    Returns:
        Tool kind and MCP server label when the tool is MCP.

    """
    if tool_name == knowledge_tool_name:
        return ProjectedToolKind.FILE_SEARCH, None

    if tool_name in mcp_tool_servers:
        return ProjectedToolKind.MCP, mcp_tool_servers[tool_name]

    for server_label in dict.fromkeys(mcp_tool_servers.values()):
        prefix = f"{server_label}_"
        if tool_name.startswith(prefix) and len(tool_name) > len(prefix):
            return ProjectedToolKind.MCP, server_label

    if tool_name.startswith(_MCP_NAME_PREFIX) and len(tool_name) > len(
        _MCP_NAME_PREFIX
    ):
        stripped = tool_name.removeprefix(_MCP_NAME_PREFIX)
        return (
            ProjectedToolKind.MCP,
            mcp_tool_servers.get(stripped) or mcp_tool_servers.get(tool_name) or "mcp",
        )

    return ProjectedToolKind.FUNCTION, None
