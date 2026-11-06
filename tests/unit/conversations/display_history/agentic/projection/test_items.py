"""Tests for PAI message projection into display turn items."""

import uuid

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.usage import RunUsage

from conversations.display_history.agentic.models.content import TextContentPart
from conversations.display_history.agentic.models.turn_items import (
    MessageTurnItem,
    SourcesTurnItem,
    ToolCallTurnItem,
    ToolResultTurnItem,
)
from conversations.display_history.agentic.projection.items import (
    turn_items_from_messages,
)
from knowledge.types import KnowledgeMatch


def _request(*parts: ModelRequestPart) -> ModelRequest:
    return ModelRequest(parts=parts)


def _response(*parts: ModelResponsePart, finish_reason: str = "stop") -> ModelResponse:
    return ModelResponse(parts=parts, finish_reason=finish_reason)  # type: ignore[arg-type]


def test_turn_items_use_prefixed_uuid_ids() -> None:
    """Generated item ids follow the same ``{prefix}{uuid4}`` shape as run ids."""
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="hi")),
        _response(TextPart(content="there")),
    ]
    run = AgentRunResult(output="there")
    run._state.message_history = messages  # pylint: disable=protected-access
    run._state.usage = RunUsage()  # pylint: disable=protected-access

    input_items, output_items, _ = turn_items_from_messages(run.new_messages())
    assert len(input_items) == 1
    assert len(output_items) == 1
    assert isinstance(input_items[0], MessageTurnItem)
    assert input_items[0].id.startswith("msg_")
    assert output_items[0].id.startswith("msg_")
    uuid.UUID(input_items[0].id.removeprefix("msg_"))
    uuid.UUID(output_items[0].id.removeprefix("msg_"))


def test_consecutive_text_parts_stay_separate() -> None:
    """Each PAI TextPart becomes its own assistant message item."""
    messages: list[ModelMessage] = [
        _response(
            TextPart(content="Hello "),
            TextPart(content="world"),
        ),
    ]

    _, output_items, _ = turn_items_from_messages(messages)
    assert len(output_items) == 2
    assert isinstance(output_items[0], MessageTurnItem)
    assert output_items[0].content == [TextContentPart(text="Hello ")]
    assert isinstance(output_items[1], MessageTurnItem)
    assert output_items[1].content == [TextContentPart(text="world")]


def test_text_around_tool_call_keeps_order() -> None:
    """Assistant text is emitted in part order, including around tool calls."""
    messages: list[ModelMessage] = [
        _response(
            TextPart(content="before"),
            ToolCallPart(tool_name="ping", args={}, tool_call_id="call_p"),
            TextPart(content="after"),
        ),
    ]

    _, output_items, _ = turn_items_from_messages(messages)
    assert [item.kind for item in output_items] == ["message", "tool_call", "message"]
    assert isinstance(output_items[0], MessageTurnItem)
    assert output_items[0].content == [TextContentPart(text="before")]
    assert isinstance(output_items[2], MessageTurnItem)
    assert output_items[2].content == [TextContentPart(text="after")]


def test_function_tool_call_and_result() -> None:
    """Ordinary function tools keep their name and the function toolset."""
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="weather?")),
        _response(
            ToolCallPart(
                tool_name="get_weather",
                args={"city": "Brno"},
                tool_call_id="call_1",
            ),
            finish_reason="tool_call",
        ),
        _request(
            ToolReturnPart(
                tool_name="get_weather",
                content="sunny",
                tool_call_id="call_1",
            )
        ),
        _response(TextPart(content="It is sunny.")),
    ]

    input_items, output_items, documents = turn_items_from_messages(messages)
    assert len(input_items) == 1
    assert documents == []

    call = output_items[0]
    result = output_items[1]
    assert isinstance(call, ToolCallTurnItem)
    assert call.name == "get_weather"
    assert call.arguments == {"city": "Brno"}
    assert call.call_id == "call_1"
    assert call.toolset.type == "function"
    assert call.id.startswith("tc_")
    assert isinstance(result, ToolResultTurnItem)
    assert result.name == "get_weather"
    assert result.content == "sunny"
    assert result.status == "success"
    assert result.toolset.type == "function"
    assert result.id.startswith("tr_")


def test_file_search_return_emits_sources_and_citations() -> None:
    """JSON-round-tripped Knowledge matches become sources plus citations."""
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="install openshift")),
        _response(
            ToolCallPart(
                tool_name="file_search",
                args={"query": "install"},
                tool_call_id="call_fs",
            ),
            finish_reason="tool_call",
        ),
        _request(
            ToolReturnPart(
                tool_name="file_search",
                content=[
                    {
                        "content": "Install via installer.",
                        "score": 0.91,
                        "source": "https://docs.example/install",
                        "metadata": {
                            "title": "Install guide",
                            "knowledge_source": "okp",
                        },
                    }
                ],
                tool_call_id="call_fs",
            )
        ),
        _response(TextPart(content="Use the installer.")),
    ]

    _, output_items, documents = turn_items_from_messages(messages)
    call = output_items[0]
    result = output_items[1]
    sources = output_items[2]
    assert isinstance(call, ToolCallTurnItem)
    assert call.toolset.type == "file_search"
    assert isinstance(result, ToolResultTurnItem)
    assert result.toolset.type == "file_search"
    assert isinstance(sources, SourcesTurnItem)
    assert sources.origin == "tool"
    assert sources.id.startswith("fs_")
    assert sources.chunks[0].content == "Install via installer."
    assert sources.chunks[0].source == "okp"
    assert sources.chunks[0].score == 0.91
    assert len(documents) == 1
    assert documents[0].doc_title == "Install guide"
    assert str(documents[0].doc_url) == "https://docs.example/install"
    assert documents[0].source == "okp"


def test_search_knowledge_matches_are_file_search() -> None:
    """In-process KnowledgeMatch objects become sources plus citations."""
    match = KnowledgeMatch(
        content="Cluster networking.",
        score=0.8,
        source="https://docs.example/network",
        metadata={"title": "Networking", "knowledge_source": "byok"},
    )
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="network")),
        _response(
            ToolCallPart(
                tool_name="search_knowledge",
                args={"query": "network"},
                tool_call_id="call_k",
            ),
            finish_reason="tool_call",
        ),
        _request(
            ToolReturnPart(
                tool_name="search_knowledge",
                content=[match],
                tool_call_id="call_k",
            )
        ),
    ]

    _, output_items, documents = turn_items_from_messages(messages)
    assert isinstance(output_items[0], ToolCallTurnItem)
    assert output_items[0].toolset.type == "file_search"
    sources = output_items[2]
    assert isinstance(sources, SourcesTurnItem)
    assert sources.chunks[0].content == "Cluster networking."
    assert sources.chunks[0].source == "byok"
    assert documents[0].doc_title == "Networking"


def test_knowledge_json_string_payload_is_parsed() -> None:
    """A JSON string of Knowledge matches is recovered via structured_content."""
    messages: list[ModelMessage] = [
        _request(
            ToolReturnPart(
                tool_name="search_knowledge",
                content=(
                    '[{"content": "Chunk A", "score": 1.0,'
                    ' "source": "https://docs.example/a",'
                    ' "metadata": {"title": "Doc A"}}]'
                ),
                tool_call_id="call_json",
            )
        )
    ]

    input_items, _, documents = turn_items_from_messages(messages)
    assert isinstance(input_items[0], ToolResultTurnItem)
    assert isinstance(input_items[1], SourcesTurnItem)
    assert input_items[1].chunks[0].content == "Chunk A"
    assert documents[0].doc_title == "Doc A"


def test_openai_file_search_wrapper_is_not_knowledge() -> None:
    """Native OpenAI ``{results: [...]}`` payloads are not Knowledge matches."""
    messages: list[ModelMessage] = [
        _request(
            ToolReturnPart(
                tool_name="file_search",
                content={
                    "results": [
                        {
                            "text": "Chunk A",
                            "score": 1,
                            "attributes": {
                                "title": "Doc A",
                                "url": "https://docs.example/a",
                            },
                        }
                    ]
                },
                tool_call_id="call_wrap",
            )
        )
    ]

    input_items, _, documents = turn_items_from_messages(messages)
    assert len(input_items) == 1
    assert isinstance(input_items[0], ToolResultTurnItem)
    assert documents == []


def test_invalid_knowledge_rows_are_skipped() -> None:
    """Rows that are not KnowledgeMatch are dropped; valid rows still project."""
    messages: list[ModelMessage] = [
        _request(
            ToolReturnPart(
                tool_name="search_knowledge",
                content=[
                    {"not": "a match"},
                    {
                        "content": "Kept.",
                        "score": 0.5,
                        "source": "https://docs.example/kept",
                        "metadata": {"title": "Kept"},
                    },
                ],
                tool_call_id="call_skip",
            )
        )
    ]

    input_items, _, documents = turn_items_from_messages(messages)
    assert isinstance(input_items[1], SourcesTurnItem)
    assert len(input_items[1].chunks) == 1
    assert input_items[1].chunks[0].content == "Kept."
    assert documents[0].doc_title == "Kept"


def test_skills_tool_is_classified_by_name() -> None:
    """PAI skills function tools use the skills toolset."""
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="use echo")),
        _response(
            ToolCallPart(
                tool_name="load_skill",
                args={"skill_name": "echo"},
                tool_call_id="call_sk",
            ),
            finish_reason="tool_call",
        ),
        _request(
            ToolReturnPart(
                tool_name="load_skill",
                content="skill body",
                tool_call_id="call_sk",
            )
        ),
    ]

    _, output_items, _ = turn_items_from_messages(messages)
    assert isinstance(output_items[0], ToolCallTurnItem)
    assert output_items[0].toolset.type == "skills"
    assert output_items[0].name == "load_skill"
    assert isinstance(output_items[1], ToolResultTurnItem)
    assert output_items[1].toolset.type == "skills"


def test_mcp_capability_id_prefix() -> None:
    """``mcp:{server}:{tool}`` is the LCORE MCP capability-id convention."""
    messages: list[ModelMessage] = [
        _request(UserPromptPart(content="read it")),
        _response(
            ToolCallPart(
                tool_name="mcp:filesystem:read_file",
                args={"path": "/tmp/a"},
                tool_call_id="call_mcp",
            ),
            finish_reason="tool_call",
        ),
        _request(
            ToolReturnPart(
                tool_name="mcp:filesystem:read_file",
                content="hello",
                tool_call_id="call_mcp",
            )
        ),
    ]

    _, output_items, _ = turn_items_from_messages(messages)
    call = output_items[0]
    result = output_items[1]
    assert isinstance(call, ToolCallTurnItem)
    assert call.name == "read_file"
    assert call.toolset.type == "mcp"
    assert call.toolset.label == "filesystem"
    assert call.arguments == {"path": "/tmp/a"}
    assert isinstance(result, ToolResultTurnItem)
    assert result.name == "read_file"
    assert result.toolset.type == "mcp"
    assert result.toolset.label == "filesystem"


def test_native_mcp_prefix_is_not_classified() -> None:
    """OGX native ``mcp_server:`` names are ordinary function tools."""
    messages: list[ModelMessage] = [
        _response(
            ToolCallPart(
                tool_name="mcp_server:filesystem",
                args={"action": "call", "tool_name": "read_file"},
                tool_call_id="call_native",
            )
        )
    ]

    _, output_items, _ = turn_items_from_messages(messages)
    call = output_items[0]
    assert isinstance(call, ToolCallTurnItem)
    assert call.name == "mcp_server:filesystem"
    assert call.toolset.type == "function"
