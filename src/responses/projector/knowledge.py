"""Map LCORE knowledge tool returns onto file-search output items."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from knowledge.types import KnowledgeMatch
from responses.models.content import AnnotationFileCitation
from responses.models.items import FileSearchToolCallResult

_KNOWLEDGE_URL_KEYS: tuple[str, ...] = (
    "doc_url",
    "docs_url",
    "url",
    "reference_url",
)


@dataclass(frozen=True)
class PendingFileCitation:
    """File citation held until the following assistant text is closed."""

    file_id: str
    filename: str


def file_search_queries(arguments: dict[str, Any]) -> list[str]:
    """Extract file-search queries from a knowledge tool argument dict.

    Args:
        arguments: Parsed tool-call arguments.

    Returns:
        Query strings present on the call.

    """
    query = arguments.get("query")
    if isinstance(query, str) and query:
        return [query]
    queries = arguments.get("queries")
    if isinstance(queries, list):
        return [item for item in queries if isinstance(item, str) and item]
    return []


def file_search_results_from_content(
    content: Any,
) -> list[FileSearchToolCallResult]:
    """Build file-search result rows from a knowledge tool return.

    Args:
        content: Tool return payload, typically a list of knowledge matches.

    Returns:
        File-search result rows for the OpenResponses item.

    """
    if not isinstance(content, list):
        return []

    results: list[FileSearchToolCallResult] = []
    for item in content:
        result = _result_from_item(item)
        if result is not None:
            results.append(result)
    return results


def _result_from_item(item: Any) -> Optional[FileSearchToolCallResult]:
    """Convert one knowledge match or mapping into a file-search result.

    Args:
        item: Knowledge match or dict-shaped match.

    Returns:
        File-search result, or None when the value is not a match.

    """
    if isinstance(item, KnowledgeMatch):
        match_metadata = dict(item.metadata)
        return FileSearchToolCallResult(
            attributes=match_metadata or None,
            file_id=item.id,
            filename=_metadata_str(match_metadata, "title"),
            score=item.score,
            text=item.content,
        )
    if not isinstance(item, dict):
        return None
    raw_metadata = item.get("metadata")
    attributes = dict(raw_metadata) if isinstance(raw_metadata, dict) else None
    file_id = item.get("id")
    return FileSearchToolCallResult(
        attributes=attributes,
        file_id=file_id if isinstance(file_id, str) else None,
        filename=_metadata_str(attributes or {}, "title"),
        score=(
            item.get("score") if isinstance(item.get("score"), (int, float)) else None
        ),
        text=item.get("content") if isinstance(item.get("content"), str) else None,
    )


def pending_file_citations_from_content(content: Any) -> list[PendingFileCitation]:
    """Build file citations from a search_knowledge return.

    Matches without content, or without a title or URL, are skipped. Duplicate
    ``(file_id, filename)`` pairs are dropped. Index is filled in when the
    following assistant message is closed.

    Args:
        content: Tool return payload, typically a list of knowledge matches.

    Returns:
        Deduplicated citations to attach to later ``output_text``.

    """
    citations: list[PendingFileCitation] = []
    seen: set[tuple[str, str]] = set()
    for match in _knowledge_matches(content):
        citation = _pending_citation_from_match(match)
        if citation is None:
            continue
        key = (citation.file_id, citation.filename)
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)
    return citations


def file_citation_at(
    citation: PendingFileCitation, index: int
) -> AnnotationFileCitation:
    """Place a pending citation at a character index in output text.

    Args:
        citation: Citation collected from knowledge search.
        index: Character index in the assistant message.

    Returns:
        OpenResponses file citation annotation.

    """
    return AnnotationFileCitation(
        file_id=citation.file_id,
        filename=citation.filename,
        index=index,
    )


def _knowledge_matches(content: Any) -> list[KnowledgeMatch]:
    """Return knowledge matches stored on a tool return.

    Args:
        content: Tool return payload.

    Returns:
        Knowledge matches on the payload, or an empty list.

    """
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, KnowledgeMatch)]


def _pending_citation_from_match(
    match: KnowledgeMatch,
) -> Optional[PendingFileCitation]:
    """Build a pending citation from a knowledge match.

    Args:
        match: One search result from knowledge search.

    Returns:
        Citation when the match has content and a title or URL, otherwise None.

    """
    if not match.content:
        return None
    metadata = dict(match.metadata)
    title = _metadata_str(metadata, "title")
    url = _url_from_match(match, metadata)
    if not title and not url:
        return None
    filename = title or _filename_from_url(url) or match.id
    file_id = (
        _metadata_str(metadata, "document_id")
        or _metadata_str(metadata, "doc_id")
        or match.id
    )
    return PendingFileCitation(file_id=file_id, filename=filename)


def _url_from_match(
    match: KnowledgeMatch, metadata: Mapping[str, Any]
) -> Optional[str]:
    """Return a citation URL from a match source or metadata.

    Args:
        match: One search result from knowledge search.
        metadata: Match metadata as a dict.

    Returns:
        URL string when one is present, otherwise None.

    """
    if match.source:
        return match.source
    for key in _KNOWLEDGE_URL_KEYS:
        value = _metadata_str(metadata, key)
        if value:
            return value
    return None


def _filename_from_url(url: Optional[str]) -> Optional[str]:
    """Use the URL path basename as a file label.

    Args:
        url: Document URL from the match.

    Returns:
        File name shown on the citation, or None when the URL has no path.

    """
    if not url:
        return None
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1] if path else ""
    return name or None


def _metadata_str(metadata: Mapping[str, Any], key: str) -> Optional[str]:
    """Return a non-empty string metadata value.

    Args:
        metadata: Match metadata.
        key: Metadata key to read.

    Returns:
        The string value, or None when missing or empty.

    """
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
