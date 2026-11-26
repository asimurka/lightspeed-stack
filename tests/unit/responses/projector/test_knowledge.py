"""Tests for knowledge-search result mapping."""

from knowledge.types import KnowledgeMatch
from responses.projector.knowledge import (
    file_search_queries,
    file_search_results_from_content,
)


class TestFileSearchResults:
    """Knowledge matches become file_search_call result rows."""

    def test_match_maps_to_result_row(self) -> None:
        """A knowledge match maps to a file search result row."""
        match = KnowledgeMatch(
            content="Cluster networking.",
            score=0.8,
            id="chunk-1",
            source="https://docs.example/network",
            metadata={"title": "Networking", "document_id": "doc-1"},
        )
        results = file_search_results_from_content([match])
        assert len(results) == 1
        assert results[0].file_id == "chunk-1"
        assert results[0].filename == "Networking"
        assert results[0].text == "Cluster networking."
        assert results[0].score == 0.8
        assert results[0].attributes == {
            "title": "Networking",
            "document_id": "doc-1",
        }

    def test_queries_from_arguments(self) -> None:
        """search_knowledge exposes a single query string as a one-element list."""
        assert file_search_queries({"query": "pods"}) == ["pods"]
        assert file_search_queries({}) == []
