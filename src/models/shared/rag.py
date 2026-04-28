"""Shared RAG-related models."""

from typing import Any, Optional

from pydantic import AnyUrl, BaseModel, Field


class RAGChunk(BaseModel):
    """Model representing a RAG chunk used in the response."""

    content: str = Field(description="The content of the chunk")
    source: Optional[str] = Field(
        default=None,
        description="Index name identifying the knowledge source from configuration",
    )
    score: Optional[float] = Field(default=None, description="Relevance score")
    attributes: Optional[dict[str, Any]] = Field(
        default=None,
        description="Document metadata from the RAG provider (e.g., url, title, author)",
    )


class ReferencedDocument(BaseModel):
    """Model representing a document referenced in generating a response.

    Attributes:
        doc_url: Url to the referenced doc.
        doc_title: Title of the referenced doc.
    """

    doc_url: Optional[AnyUrl] = Field(
        default=None, description="URL of the referenced document"
    )

    doc_title: Optional[str] = Field(
        default=None, description="Title of the referenced document"
    )

    source: Optional[str] = Field(
        default=None,
        description="Index name identifying the knowledge source from configuration",
    )


class RAGContext(BaseModel):
    """Result of building RAG context from all enabled pre-query RAG sources.

    Attributes:
        context_text: Formatted RAG context string for injection into the query.
        rag_chunks: RAG chunks from pre-query sources (BYOK + Solr).
        referenced_documents: Referenced documents from pre-query sources.
    """

    context_text: str = Field(default="", description="Formatted context for injection")
    rag_chunks: list[RAGChunk] = Field(
        default_factory=list,
        description="RAG chunks from pre-query sources",
    )
    referenced_documents: list[ReferencedDocument] = Field(
        default_factory=list,
        description="Documents from pre-query sources",
    )


__all__ = ["RAGChunk", "ReferencedDocument", "RAGContext"]
