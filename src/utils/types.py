"""Common types for the project."""

from typing import Any

from llama_stack_api import ImageContentItem, TextContentItem

from models.shared.conversation_resolve import ResponsesConversationContext
from models.shared.rag import RAGChunk, RAGContext, ReferencedDocument
from models.shared.responses_llama import IncludeParameter, ResponseInput, ResponseItem
from models.shared.responses_params import ResponsesApiParams
from models.shared.shields import (
    ShieldModerationBlocked,
    ShieldModerationPassed,
    ShieldModerationResult,
)
from models.shared.tools import ToolCallSummary, ToolResultSummary
from models.shared.transcripts import Transcript, TranscriptMetadata, TurnSummary

type SingletonInstances = dict[type, Any]


def content_to_str(content: Any) -> str:
    """Convert content (str, TextContentItem, ImageContentItem, or list) to string.

    Parameters:
    ----------
        content: Value to normalize into a string (may be None,
                 str, content item, list, or any other object).

    Returns:
    -------
        str: The normalized string representation of the content.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, TextContentItem):
        return content.text
    if isinstance(content, ImageContentItem):
        return "<image>"
    if isinstance(content, list):
        return " ".join(content_to_str(item) for item in content)
    return str(content)


class Singleton(type):
    """Metaclass for Singleton support."""

    _instances: SingletonInstances = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Return the single cached instance of the class, creating and caching it on first call.

        Returns:
            object: The singleton instance for this class.
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


__all__ = [
    "IncludeParameter",
    "ResponseItem",
    "ResponseInput",
    "ResponsesApiParams",
    "ResponsesConversationContext",
    "ToolCallSummary",
    "ToolResultSummary",
    "RAGChunk",
    "ReferencedDocument",
    "RAGContext",
    "TurnSummary",
    "TranscriptMetadata",
    "Transcript",
    "ShieldModerationPassed",
    "ShieldModerationBlocked",
    "ShieldModerationResult",
    "Singleton",
    "content_to_str",
]
