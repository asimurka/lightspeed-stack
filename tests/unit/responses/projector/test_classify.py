"""Tests for Responses projector tool classification."""

from responses.projector.classify import (
    ProjectedToolKind,
    classify_tool,
    mcp_tool_name,
    parse_mcp_tool_name,
)


def _mcp_groups(tool_name: str) -> dict[str, str] | None:
    """Return named regex groups, or None when the tool name is not MCP."""
    match = parse_mcp_tool_name(tool_name)
    return match.groupdict() if match else None


class TestParseMcpToolName:
    """parse_mcp_tool_name decodes prefix_tools(f"mcp:{label}:") names."""

    def test_label_and_bare_name(self) -> None:
        """mcp:{label}:_{bare} yields the server label and MCP tool name."""
        assert _mcp_groups("mcp:jira:_create_issue") == {
            "label": "jira",
            "bare": "create_issue",
        }

    def test_underscores_in_label_and_bare_name(self) -> None:
        """Underscores inside the label or bare name stay part of that field."""
        assert _mcp_groups("mcp:my_jira:_run_query_v2") == {
            "label": "my_jira",
            "bare": "run_query_v2",
        }

    def test_legacy_mcp_underscore_prefix_is_not_mcp(self) -> None:
        """The old mcp_ prefix is not the encoded MCP form."""
        assert parse_mcp_tool_name("mcp_create_issue") is None

    def test_missing_separator_is_not_mcp(self) -> None:
        """A colon without the PAI underscore join is not MCP."""
        assert parse_mcp_tool_name("mcp:jira:create_issue") is None

    def test_empty_label_or_bare_name_is_not_mcp(self) -> None:
        """Both the label and bare name must be non-empty."""
        assert parse_mcp_tool_name("mcp::_create_issue") is None
        assert parse_mcp_tool_name("mcp:jira:_") is None


class TestMcpToolName:
    """mcp_tool_name is the OpenResponses mcp_call.name field."""

    def test_strips_namespace_and_label(self) -> None:
        """The item name is the bare MCP tool, not the PAI-prefixed string."""
        assert mcp_tool_name("mcp:jira:_create_issue") == "create_issue"

    def test_unprefixed_name_is_unchanged(self) -> None:
        """Non-MCP names pass through for callers that do not pre-classify."""
        assert mcp_tool_name("get_weather") == "get_weather"


class TestClassifyTool:
    """classify_tool maps agent-loop names onto OpenResponses item kinds."""

    def test_knowledge_tool_is_file_search(self) -> None:
        """The LCORE knowledge tool becomes file_search_call."""
        kind, label = classify_tool("search_knowledge")
        assert kind is ProjectedToolKind.FILE_SEARCH
        assert label is None

    def test_prefixed_mcp_tool(self) -> None:
        """Encoded MCP names project as mcp_call with the parsed server label."""
        kind, label = classify_tool("mcp:jira:_create_issue")
        assert kind is ProjectedToolKind.MCP
        assert label == "jira"

    def test_prefixed_mcp_tool_with_underscore_label(self) -> None:
        """Labels may contain underscores; the first :_ is the split."""
        kind, label = classify_tool("mcp:my_jira:_lookup_topic")
        assert kind is ProjectedToolKind.MCP
        assert label == "my_jira"

    def test_bare_name_without_prefix_is_function(self) -> None:
        """Tool names without the MCP encoding stay generic functions."""
        kind, label = classify_tool("create_issue")
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_legacy_mcp_prefix_is_function(self) -> None:
        """mcp_ without mcp:{label}:_ is a generic function, not MCP."""
        kind, label = classify_tool("mcp_create_issue")
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_skills_stay_function(self) -> None:
        """Skills in-loop tools stay generic functions."""
        kind, label = classify_tool("load_skill")
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_generic_function(self) -> None:
        """Unrelated in-loop tools stay generic functions."""
        kind, label = classify_tool("get_weather")
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_native_file_search_name_is_not_special(self) -> None:
        """Native file-search leftover names stay generic functions."""
        kind, label = classify_tool("file_search")
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None
