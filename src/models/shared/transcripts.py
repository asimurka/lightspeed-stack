"""Shared transcript models."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from models.shared.rag import RAGChunk, ReferencedDocument
from models.shared.tools import ToolCallSummary, ToolResultSummary
from utils.token_counter import TokenCounter


class TurnSummary(BaseModel):
    """Summary of a turn in llama stack."""

    id: str = Field(default="", description="ID of the response")
    llm_response: str = ""
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    tool_results: list[ToolResultSummary] = Field(default_factory=list)
    rag_chunks: list[RAGChunk] = Field(default_factory=list)
    referenced_documents: list[ReferencedDocument] = Field(default_factory=list)
    token_usage: TokenCounter = Field(default_factory=TokenCounter)


class TranscriptMetadata(BaseModel):
    """Metadata for a transcript entry."""

    provider: Optional[str] = None
    model: str
    query_provider: Optional[str] = None
    query_model: Optional[str] = None
    user_id: str
    conversation_id: str
    timestamp: str


class Transcript(BaseModel):
    """Model representing a transcript entry to be stored."""

    metadata: TranscriptMetadata
    redacted_query: str
    query_is_valid: bool
    llm_response: str
    rag_chunks: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["TurnSummary", "TranscriptMetadata", "Transcript"]
