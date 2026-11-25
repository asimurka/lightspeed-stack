"""Tests for knowledge-search result and citation mapping."""

from knowledge.types import KnowledgeMatch
from responses.projector.knowledge import (
    file_citation_at,
    pending_file_citations_from_content,
)


class TestPendingFileCitations:
    """Knowledge matches become file citations the way display history cites them."""

    def test_title_and_url_become_citation(self) -> None:
        """A match with content and title is cited."""
        match = KnowledgeMatch(
            content="Cluster networking.",
            score=0.8,
            id="chunk-1",
            source="https://docs.example/network",
            metadata={"title": "Networking", "document_id": "doc-1"},
        )
        citations = pending_file_citations_from_content([match])
        assert len(citations) == 1
        assert citations[0].file_id == "doc-1"
        assert citations[0].filename == "Networking"
        annotation = file_citation_at(citations[0], 12)
        assert annotation.file_id == "doc-1"
        assert annotation.filename == "Networking"
        assert annotation.index == 12

    def test_skips_empty_content_and_missing_title_or_url(self) -> None:
        """Empty matches and matches without a title or URL are not cited."""
        citations = pending_file_citations_from_content(
            [
                KnowledgeMatch(
                    content="",
                    score=1.0,
                    source="https://docs.example/empty",
                    metadata={"title": "Empty"},
                ),
                KnowledgeMatch(content="No citation metadata.", score=0.1),
                KnowledgeMatch(
                    content="Kept.",
                    score=0.5,
                    source="https://docs.example/kept",
                    metadata={"title": "Kept"},
                ),
            ]
        )
        assert len(citations) == 1
        assert citations[0].filename == "Kept"

    def test_url_basename_when_title_missing(self) -> None:
        """A URL-only match uses the path basename as the filename."""
        match = KnowledgeMatch(
            content="Kept.",
            score=0.5,
            source="https://docs.example/path/pods.html",
        )
        citations = pending_file_citations_from_content([match])
        assert citations[0].filename == "pods.html"
