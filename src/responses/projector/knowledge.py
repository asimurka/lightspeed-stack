"""Map knowledge search tool results to file_search_call fields."""

from typing import Any, Optional

from knowledge.types import KnowledgeMatch
from responses.models.items import FileSearchToolCallResult


def file_search_queries(arguments: dict[str, Any]) -> list[str]:
    """Read ``search_knowledge``'s single query as a one-element list.

    Args:
        arguments: Parsed tool call arguments.

    Returns:
        ``[query]`` when present, otherwise an empty list.

    """
    query = arguments.get("query")
    if isinstance(query, str) and query:
        return [query]
    return []


def file_search_results_from_content(
    content: Any,
) -> list[FileSearchToolCallResult]:
    """Build file_search_call result rows from a tool return payload.

    Args:
        content: Tool return, usually a list of knowledge matches.

    Returns:
        Result rows for the file_search_call item.

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
    """Convert one match value into a file search result row.

    Args:
        item: Knowledge match or dict-shaped match.

    Returns:
        Result row, or None when the value is not a match.

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


def _metadata_str(metadata: dict[str, Any], key: str) -> Optional[str]:
    """Read a non-empty string value from match metadata.

    Args:
        metadata: Match metadata.
        key: Metadata key.

    Returns:
        String value, or None when missing or empty.

    """
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
