"""Convert PAI messages into display-history turn items."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, Optional
from urllib.parse import urlparse

from pydantic import AnyUrl, TypeAdapter, ValidationError
from pydantic_ai.messages import (
    BinaryContent,
    DocumentUrl,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextContent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UploadedFile,
    UserPromptPart,
)

from constants import DEFAULT_RAG_TOOL
from conversations.agent_history.ids import turn_item_id
from conversations.display_history.agentic.models.content import (
    FileContentPart,
    ImageContentPart,
    MessageContent,
    MessageContentPart,
    TextContentPart,
)
from conversations.display_history.agentic.models.turn_items import (
    MessageTurnItem,
    ReasoningTurnItem,
    SourceChunk,
    SourcesTurnItem,
    ToolCallTurnItem,
    ToolResultTurnItem,
    ToolsetInfo,
    TurnItem,
)
from conversations.display_history.agentic.models.types import ToolResultBody
from knowledge.types import KnowledgeMatch
from models.common.turn_summary import ReferencedDocument

_IMAGE_MEDIA_PREFIX = "image/"
_MCP_TOOLSET_ID_PREFIX: Final[str] = "mcp:"
_KNOWLEDGE_TOOL_NAME: Final[str] = "search_knowledge"
_FILE_SEARCH_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {DEFAULT_RAG_TOOL, _KNOWLEDGE_TOOL_NAME}
)
_SKILLS_TOOL_NAMES: Final[frozenset[str]] = frozenset(
    {"list_skills", "load_skill", "read_skill_resource", "run_skill_script"}
)
_KNOWLEDGE_MATCH: Final[TypeAdapter[KnowledgeMatch]] = TypeAdapter(KnowledgeMatch)
_KNOWLEDGE_URL_KEYS: Final[tuple[str, ...]] = (
    "doc_url",
    "docs_url",
    "url",
    "reference_url",
)


def turn_items_from_messages(
    messages: list[ModelMessage],
) -> tuple[list[TurnItem], list[TurnItem], list[ReferencedDocument]]:
    """Split a run's new messages into input items, output items, and citations.

    Request parts before the first model response start the turn (user prompt
    or a deferred tool reply). Everything from the first response onward is
    output, including in-loop tool returns on later requests.

    MCP, file search, and skills arrive as ``ToolCallPart`` / ``ToolReturnPart``.
    Family (``mcp``, ``file_search``, ``skills``, ``function``) is classified
    from LCORE tool names, not from native PAI tool parts.

    Args:
        messages: PAI ``new_messages()`` for one run.

    Returns:
        Input items, output items, and referenced documents found in tools.

    """
    input_items: list[TurnItem] = []
    output_items: list[TurnItem] = []
    documents: list[ReferencedDocument] = []
    seen_response = False

    for message in messages:
        if isinstance(message, ModelResponse):
            seen_response = True
            items, extra_docs = _items_from_response(message)
            output_items.extend(items)
            documents.extend(extra_docs)
        elif isinstance(message, ModelRequest):
            items, extra_docs = _items_from_request(message)
            target = output_items if seen_response else input_items
            target.extend(items)
            documents.extend(extra_docs)

    return input_items, output_items, documents


def _items_from_request(
    message: ModelRequest,
) -> tuple[list[TurnItem], list[ReferencedDocument]]:
    """Convert user prompts and function tool returns on a request."""
    items: list[TurnItem] = []
    documents: list[ReferencedDocument] = []
    for part in message.parts:
        if isinstance(part, UserPromptPart):
            content = _message_content_from_user_prompt(part.content)
            if not content:
                continue
            items.append(
                MessageTurnItem(
                    id=turn_item_id("message"),
                    role="user",
                    content=content,
                )
            )
        elif isinstance(part, ToolReturnPart):
            extra_items, extra_docs = _tool_result_items(part)
            items.extend(extra_items)
            documents.extend(extra_docs)
    return items, documents


def _items_from_response(
    message: ModelResponse,
) -> tuple[list[TurnItem], list[ReferencedDocument]]:
    """Convert assistant text, reasoning, and tool activity on a response."""
    items: list[TurnItem] = []
    documents: list[ReferencedDocument] = []

    for part in message.parts:
        if isinstance(part, TextPart):
            items.append(
                MessageTurnItem(
                    id=turn_item_id("message"),
                    role="assistant",
                    content=[TextContentPart(text=part.content)],
                )
            )
        elif isinstance(part, ThinkingPart):
            items.append(
                ReasoningTurnItem(
                    id=turn_item_id("reasoning", part.id),
                    content=part.content,
                )
            )
        elif isinstance(part, ToolCallPart):
            items.append(_tool_call_item(part))
        elif isinstance(part, ToolReturnPart):
            extra_items, extra_docs = _tool_result_items(part)
            items.extend(extra_items)
            documents.extend(extra_docs)

    return items, documents


def _tool_call_item(part: ToolCallPart) -> ToolCallTurnItem:
    """Map a function tool call, including LCORE MCP / file search / skills."""
    name, toolset = _classify_tool(part.tool_name)
    return ToolCallTurnItem(
        id=turn_item_id("tool_call", part.id),
        call_id=part.tool_call_id,
        name=name,
        arguments=part.args_as_dict(),
        toolset=toolset,
    )


def _tool_result_items(
    part: ToolReturnPart,
) -> tuple[list[TurnItem], list[ReferencedDocument]]:
    """Map a function tool return, plus sources when the tool is file search."""
    name, toolset = _classify_tool(part.tool_name)
    result = ToolResultTurnItem(
        id=turn_item_id("tool_result"),
        call_id=part.tool_call_id,
        name=name,
        status=part.outcome,
        content=_tool_result_body(part.content, fallback=part.model_response_str()),
        toolset=toolset,
    )
    items: list[TurnItem] = [result]
    if toolset.type != "file_search":
        return items, []
    sources, documents = _sources_from_knowledge(part)
    if sources is not None:
        items.append(sources)
    return items, documents


def _classify_tool(tool_name: str) -> tuple[str, ToolsetInfo]:
    """Return the display name and tool family for an LCORE function tool.

    Recognition is by tool name (and the ``mcp:{server}`` capability-id
    prefix from the PAI tools migration), not by native PAI part types.
    """
    match tool_name:
        case name if name in _FILE_SEARCH_TOOL_NAMES:
            return name, ToolsetInfo(type="file_search")
        case name if name in _SKILLS_TOOL_NAMES:
            return name, ToolsetInfo(type="skills")
        case "web_search":
            return tool_name, ToolsetInfo(type="web_search")
        case name if name.startswith(_MCP_TOOLSET_ID_PREFIX):
            return _classify_mcp_tool(name)
        case _:
            return tool_name, ToolsetInfo(type="function")


def _classify_mcp_tool(tool_name: str) -> tuple[str, ToolsetInfo]:
    """Split ``mcp:{server}`` or ``mcp:{server}:{tool}`` into name and label."""
    rest = tool_name.removeprefix(_MCP_TOOLSET_ID_PREFIX)
    server, separator, inner = rest.partition(":")
    if separator and inner:
        return inner, ToolsetInfo(type="mcp", label=server)
    return rest or tool_name, ToolsetInfo(type="mcp", label=server or None)


def _sources_from_knowledge(
    part: ToolReturnPart,
) -> tuple[Optional[SourcesTurnItem], list[ReferencedDocument]]:
    """Build a sources item and citations from a Knowledge tool return."""
    chunks: list[SourceChunk] = []
    documents: list[ReferencedDocument] = []
    seen_docs: set[tuple[str, str]] = set()
    for match in _knowledge_matches(part):
        if not match.content:
            continue
        chunks.append(_source_chunk_from_match(match))
        document = _referenced_document_from_match(match)
        if document is None:
            continue
        key = (str(document.doc_url or ""), document.doc_title or "")
        if key in seen_docs:
            continue
        seen_docs.add(key)
        documents.append(document)

    if not chunks:
        return None, documents
    sources = SourcesTurnItem(
        id=turn_item_id("file_search_sources"),
        origin="tool",
        chunks=chunks,
    )
    return sources, documents


def _knowledge_matches(part: ToolReturnPart) -> list[KnowledgeMatch]:
    """Parse Knowledge tool output as ``list[KnowledgeMatch]``.

    Accepts in-process dataclasses, JSON-round-tripped dicts, and a JSON
    string via ``structured_content()``. Rows that are not matches are skipped.
    """
    payload: Any = part.structured_content()
    if payload is None:
        payload = part.content
    if not isinstance(payload, list):
        return []
    matches: list[KnowledgeMatch] = []
    for item in payload:
        try:
            matches.append(_KNOWLEDGE_MATCH.validate_python(item))
        except ValidationError:
            continue
    return matches


def _source_chunk_from_match(match: KnowledgeMatch) -> SourceChunk:
    """Map one Knowledge match onto a display retrieval chunk."""
    metadata = dict(match.metadata)
    return SourceChunk(
        content=match.content,
        source=_metadata_str(metadata, "knowledge_source") or match.source,
        score=match.score,
        attributes=metadata or None,
    )


def _referenced_document_from_match(
    match: KnowledgeMatch,
) -> Optional[ReferencedDocument]:
    """Build a citation from match source and Knowledge metadata."""
    metadata = match.metadata
    title = _metadata_str(metadata, "title")
    doc_url = _url_from_match(match)
    if not title and doc_url is None:
        return None
    return ReferencedDocument(
        doc_title=title,
        doc_url=doc_url,
        source=_metadata_str(metadata, "knowledge_source"),
        document_id=_metadata_str(metadata, "document_id")
        or _metadata_str(metadata, "doc_id"),
    )


def _url_from_match(match: KnowledgeMatch) -> Optional[AnyUrl]:
    """Prefer ``match.source`` when it is a URI, else known metadata URL keys."""
    if parsed := _parse_url(match.source):
        return parsed
    for key in _KNOWLEDGE_URL_KEYS:
        if parsed := _parse_url(_metadata_str(match.metadata, key)):
            return parsed
    return None


def _metadata_str(metadata: Mapping[str, Any], key: str) -> Optional[str]:
    """Return a non-empty string metadata value."""
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _parse_url(value: Optional[str]) -> Optional[AnyUrl]:
    """Parse an absolute URI, or return None when the value is not a URL."""
    if not value:
        return None
    try:
        return AnyUrl(value)
    except ValidationError:
        return None


def _tool_result_body(content: Any, fallback: str = "") -> ToolResultBody:
    """Keep structured tool output when it is JSON-shaped, else stringify."""
    if isinstance(content, (str, dict, list)):
        return content
    return fallback or str(content)


def _message_content_from_user_prompt(
    content: str | Sequence[Any],
) -> MessageContent:
    """Project a user prompt into display content (no raw binary)."""
    if isinstance(content, str):
        return [TextContentPart(text=content)] if content else []
    parts: list[MessageContentPart] = []
    for item in content:
        converted = _user_content_part(item)
        if converted is not None:
            parts.append(converted)
    return parts


def _user_content_part(  # pylint: disable=too-many-return-statements
    item: Any,
) -> Optional[MessageContentPart]:
    """Map one PAI user-content value onto a display content part."""
    if isinstance(item, str):
        return TextContentPart(text=item) if item else None
    if isinstance(item, TextContent):
        return TextContentPart(text=item.content) if item.content else None
    if isinstance(item, ImageUrl):
        return _image_from_url(item.url)
    if isinstance(item, DocumentUrl):
        return FileContentPart(filename=_filename_from_url(item.url))
    if isinstance(item, UploadedFile):
        media_type = getattr(item, "media_type", None) or ""
        if str(media_type).startswith(_IMAGE_MEDIA_PREFIX):
            return ImageContentPart(file_id=item.file_id)
        return FileContentPart(file_id=item.file_id)
    if isinstance(item, BinaryContent):
        return None
    return None


def _image_from_url(url: str) -> Optional[ImageContentPart]:
    """Build an image part when the URL is a valid absolute URI."""
    try:
        return ImageContentPart(image_url=AnyUrl(url))
    except ValidationError:
        return None


def _filename_from_url(url: str) -> str:
    """Use the URL path basename, or the raw URL, as a file label."""
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1] if path else ""
    return name or url
