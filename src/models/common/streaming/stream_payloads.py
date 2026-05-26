"""Typed JSON bodies for SSE streaming events."""

import json
from typing import Annotated, Literal, Optional, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from models.common import ReferencedDocument, ToolCallSummary, ToolResultSummary


class StreamPayloadBase(BaseModel):
    """Base for streaming SSE JSON payloads."""

    model_config = ConfigDict(extra="forbid")

    def serialize_json(self) -> str:
        """Format this payload as an SSE ``data:`` line."""
        return f"data: {json.dumps(self.model_dump(mode='json'))}\n\n"

    def serialize_text(self) -> str:
        """Format this payload as plain text for text media type clients."""
        return ""


class ErrorEventData(BaseModel):
    """Payload for event: "error"."""

    status_code: int
    response: str
    cause: str


class StartEventData(BaseModel):
    """Payload for event: "start"."""

    conversation_id: str
    request_id: str


class InterruptedEventData(BaseModel):
    """Payload for event: "interrupted"."""

    request_id: str


class EndEventData(BaseModel):
    """Nested data for event: "end"."""

    referenced_documents: list[ReferencedDocument]
    truncated: Optional[bool]
    input_tokens: int
    output_tokens: int


class ErrorStreamPayload(StreamPayloadBase):
    """SSE error event body (event + typed data)."""

    event: Literal["error"] = "error"
    data: ErrorEventData

    def serialize_text(self) -> str:
        """Serialize error stream payload to plain text."""
        return f"Status: {self.data.status_code} - {self.data.response} - {self.data.cause}"


class StartStreamPayload(StreamPayloadBase):
    """SSE stream start body."""

    event: Literal["start"] = "start"
    data: StartEventData


class InterruptedStreamPayload(StreamPayloadBase):
    """SSE interrupted stream body."""

    event: Literal["interrupted"] = "interrupted"
    data: InterruptedEventData


class EndStreamPayload(StreamPayloadBase):
    """SSE end-of-stream body (includes available_quotas beside data)."""

    event: Literal["end"] = "end"
    data: EndEventData
    available_quotas: dict[str, int]

    def serialize_text(self) -> str:
        """Serialize end stream payload to plain text."""
        ref_docs_string = "\n".join(
            f"{doc.doc_title}: {doc.doc_url}"
            for doc in self.data.referenced_documents
            if doc.doc_url and doc.doc_title
        )
        return f"\n\n---\n\n{ref_docs_string}" if ref_docs_string else ""


class TokenChunkData(BaseModel):
    """Structured data for token and turn-complete stream lines."""

    id: int
    token: str


class TokenStreamPayload(StreamPayloadBase):
    """SSE token delta (event: "token")."""

    event: Literal["token"] = "token"
    data: TokenChunkData

    def serialize_text(self) -> str:
        """Serialize token stream payload to plain text."""
        return self.data.token


class TurnCompleteStreamPayload(StreamPayloadBase):
    """SSE turn completion (same data shape as token)."""

    event: Literal["turn_complete"] = "turn_complete"
    data: TokenChunkData


class ToolCallStreamPayload(StreamPayloadBase):
    """SSE tool call summary."""

    event: Literal["tool_call"] = "tool_call"
    data: ToolCallSummary

    def serialize_text(self) -> str:
        """Serialize tool call stream payload to plain text."""
        return f"[Tool Call: {self.data.name}]\n"


class ToolResultStreamPayload(StreamPayloadBase):
    """SSE tool result summary."""

    event: Literal["tool_result"] = "tool_result"
    data: ToolResultSummary

    def serialize_text(self) -> str:
        """Serialize tool result stream payload to plain text."""
        return "[Tool Result]\n"


StreamEventPayload: TypeAlias = Annotated[
    TokenStreamPayload
    | TurnCompleteStreamPayload
    | ToolCallStreamPayload
    | ToolResultStreamPayload
    | EndStreamPayload
    | ErrorStreamPayload
    | InterruptedStreamPayload
    | StartStreamPayload,
    Field(discriminator="event"),
]
