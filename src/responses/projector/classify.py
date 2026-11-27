"""Map agent tool names to OpenResponses tool item kinds."""

import re
from enum import StrEnum
from typing import Final, Optional

KNOWLEDGE_TOOL_NAME = "search_knowledge"
_MCP_TOOL_NAME: Final[re.Pattern[str]] = re.compile(
    r"mcp:(?P<label>[^:]+):_(?P<bare>.+)"
)


class ProjectedToolKind(StrEnum):
    """OpenResponses output item kind for an in-loop or deferred tool."""

    FUNCTION = "function"
    MCP = "mcp"
    FILE_SEARCH = "file_search"


def parse_mcp_tool_name(tool_name: str) -> Optional[re.Match[str]]:
    """Parse a PAI PrefixedToolset MCP name of the form mcp:{label}:_{bare}.

    prefix_tools(f"mcp:{label}:") joins prefix and bare name with an underscore,
    so the on-the-wire name is mcp:{label}:_{bare}. The server label must not
    contain a colon; the bare MCP tool name may contain underscores.

    Args:
        tool_name: Tool name on the call or return.

    Returns:
        A regex match with groups label and bare, or None when the name is not
        MCP.

    """
    return _MCP_TOOL_NAME.fullmatch(tool_name)


def mcp_tool_name(tool_name: str) -> str:
    """Return the bare MCP tool name encoded in a prefixed PAI tool name.

    Args:
        tool_name: Tool name from the agent.

    Returns:
        Bare MCP tool name after mcp:{label}:_, or tool_name if unprefixed.

    """
    if (match := parse_mcp_tool_name(tool_name)):
        return match.group("bare")
    return tool_name


def classify_tool(tool_name: str) -> tuple[ProjectedToolKind, Optional[str]]:
    """Classify an agent tool name for OpenResponses projection.

    MCP tools use the PAI prefix_tools(f"mcp:{label}:") form
    mcp:{label}:_{bare}. The server label is taken from the name.

    Args:
        tool_name: Tool name on the call or return.

    Returns:
        Item kind and MCP server label when the tool is MCP.

    """
    if tool_name == KNOWLEDGE_TOOL_NAME:
        return ProjectedToolKind.FILE_SEARCH, None

    if (match := parse_mcp_tool_name(tool_name)):
        return ProjectedToolKind.MCP, match.group("label")
    return ProjectedToolKind.FUNCTION, None
