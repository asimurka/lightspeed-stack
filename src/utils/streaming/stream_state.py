"""Mutable streaming loop state for Responses API SSE generation."""

from dataclasses import dataclass, field
from typing import Optional

from llama_stack_api import OpenAIResponseObject

from constants import MEDIA_TYPE_JSON
from models.context import ResponseGeneratorContext
from utils.types import TurnSummary


@dataclass
class StreamProcessingState:
    """Holds mutable state while streaming a single model response.

    Attributes:
        turn_summary: Incrementally built representation of the assistant turn
        context: Request-level configuration.
        chunk_id: Identifier used to order streamed chunks.
        text_parts: Collected fragments of assistant text.
        pending_mcp_calls: Mapping of in-progress MCP tool calls, keyed by call index,
            storing (call_id, tool_name) until arguments are fully received.
        latest_response_object: Final response object after streaming ends.
    """

    turn_summary: TurnSummary
    context: ResponseGeneratorContext
    chunk_id: int = 0
    text_parts: list[str] = field(default_factory=list)
    pending_mcp_calls: dict[int, tuple[str, str]] = field(default_factory=dict)
    latest_response_object: Optional[OpenAIResponseObject] = None

    @property
    def media_type(self) -> str:
        """Resolved client media type (same default as elsewhere on the request)."""
        return self.context.query_request.media_type or MEDIA_TYPE_JSON
