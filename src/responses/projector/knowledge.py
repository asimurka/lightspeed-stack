"""Map knowledge search tool results to file_search_call fields."""

from collections.abc import Sequence
from typing import Any

from knowledge.types import KnowledgeMatch
from responses.models.items import FileSearchToolCallResult


def file_search_queries(arguments: dict[str, Any]) -> list[str]:
    """Return the search_knowledge query as a one-element list when set."""
    query = arguments.get("query")
    return [query] if isinstance(query, str) and query else []


def knowledge_matches_from_return(content: object) -> list[KnowledgeMatch]:
    """Parse search_knowledge tool return content into knowledge matches."""
    if not isinstance(content, list):
        return []
    return [match for match in content if isinstance(match, KnowledgeMatch)]


def file_search_results_from_matches(
    matches: Sequence[KnowledgeMatch],
) -> list[FileSearchToolCallResult]:
    """Build file_search_call result rows from knowledge matches."""
    return [
        FileSearchToolCallResult(
            attributes=dict(match.metadata),
            file_id=match.id,
            filename=match.metadata.get("title"),
            score=match.score,
            text=match.content,
        )
        for match in matches
    ]
