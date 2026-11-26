"""Tests for Responses projector tool classification."""

from responses.projector.classify import ProjectedToolKind, classify_tool


class TestClassifyTool:
    """classify_tool maps agent-loop names onto OpenResponses item kinds."""

    def test_knowledge_tool_is_file_search(self) -> None:
        """The LCORE knowledge tool becomes file_search_call."""
        kind, label = classify_tool("search_knowledge", {})
        assert kind is ProjectedToolKind.FILE_SEARCH
        assert label is None

    def test_mapped_mcp_tool(self) -> None:
        """mcp_-prefixed tools use the bare name to look up server label."""
        kind, label = classify_tool("mcp_create_issue", {"create_issue": "jira"})
        assert kind is ProjectedToolKind.MCP
        assert label == "jira"

    def test_mcp_toolset_prefix(self) -> None:
        """PAI MCP toolset names use the mcp_ prefix."""
        kind, label = classify_tool("mcp_lookup_topic", {"lookup_topic": "docs"})
        assert kind is ProjectedToolKind.MCP
        assert label == "docs"

    def test_mcp_toolset_prefix_without_map(self) -> None:
        """Unmapped mcp_ names are still MCP, with a generic server label."""
        kind, label = classify_tool("mcp_lookup_topic", {})
        assert kind is ProjectedToolKind.MCP
        assert label == "mcp"

    def test_bare_name_without_prefix_is_function(self) -> None:
        """Tool names without mcp_ stay generic functions even when configured."""
        kind, label = classify_tool("create_issue", {"create_issue": "jira"})
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_skills_stay_function(self) -> None:
        """Skills in-loop tools stay generic functions."""
        kind, label = classify_tool("load_skill", {})
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_generic_function(self) -> None:
        """Unrelated in-loop tools stay generic functions."""
        kind, label = classify_tool("get_weather", {"create_issue": "jira"})
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None

    def test_native_file_search_name_is_not_special(self) -> None:
        """Native file-search leftover names stay generic functions."""
        kind, label = classify_tool("file_search", {})
        assert kind is ProjectedToolKind.FUNCTION
        assert label is None
