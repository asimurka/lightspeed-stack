"""Streaming pointers into the live OpenResponses envelope."""

from dataclasses import dataclass, field
from typing import Any, Optional

from responses.models.content import OutputTextPart
from responses.models.items import (
    FileSearchToolCall,
    FunctionToolCall,
    McpCall,
    ReasoningContent,
    ReasoningItem,
    ResponseMessage,
)
from responses.projector.knowledge import file_search_queries
from responses.projector.payload import (
    arguments_json,
    merge_argument_delta,
    parse_arguments,
)

OpenTool = FunctionToolCall | McpCall | FileSearchToolCall


@dataclass
class ItemTracker:
    """In-flight pointers into ``response.output`` (same objects, not copies)."""

    current_message: Optional[ResponseMessage] = None
    current_reasoning: Optional[ReasoningItem] = None
    open_tools: dict[str, OpenTool] = field(default_factory=dict)
    hidden_output_indices: set[int] = field(default_factory=set)
    lifecycle_started: bool = False

    def extend_message(self, chunk: str) -> None:
        """Append a delta onto the registered assistant message."""
        item = self.current_message
        if item is None:
            return
        part = open_output_text_part(item)
        if part is None:
            return
        part.text += chunk

    def extend_reasoning(self, chunk: str) -> None:
        """Append a delta onto the registered reasoning item."""
        item = self.current_reasoning
        if item is None:
            return
        part = open_reasoning_text_part(item)
        if part is None:
            return
        part.text += chunk

    def tool(self, tool_call_id: str) -> Optional[OpenTool]:
        """Return the open tool for this call id, if still in flight."""
        return self.open_tools.get(tool_call_id)

    def extend_tool(
        self,
        tool_call_id: str,
        args: str | dict[str, Any] | None,
        *,
        replace: bool = False,
    ) -> Optional[OpenTool]:
        """Apply streamed or final tool arguments to the open item.

        Function and MCP items store JSON on ``arguments``: string deltas
        append, dict deltas shallow-merge then dump, ``replace`` writes the
        final snapshot. File search ignores deltas and only maps a parsed
        ``query`` onto ``queries`` when ``replace`` is set (tool-call end).
        """
        item = self.tool(tool_call_id)
        if item is None:
            return None
        if isinstance(item, FileSearchToolCall):
            if replace:
                parsed = (
                    args
                    if isinstance(args, dict)
                    else parse_arguments(arguments_json(args))
                )
                queries = file_search_queries(parsed)
                if queries:
                    item.queries = queries
            return item
        if args is None:
            return item
        if replace:
            item.arguments = arguments_json(args)
            return item
        if isinstance(args, str):
            item.arguments += args
            return item
        item.arguments = merge_argument_delta(item.arguments, args)
        return item

    def close_tool(self, tool_call_id: str) -> None:
        """Drop an in-flight tool pointer when it is safe to do so."""
        self.open_tools.pop(tool_call_id, None)


def open_output_text_part(item: ResponseMessage) -> Optional[OutputTextPart]:
    """Return the in-progress output_text part opened at message start."""
    content = item.content
    if isinstance(content, str) or not content:
        return None
    part = content[-1]
    return part if isinstance(part, OutputTextPart) else None


def open_reasoning_text_part(item: ReasoningItem) -> Optional[ReasoningContent]:
    """Return the in-progress reasoning_text part opened at thinking start."""
    content = item.content
    if not content:
        return None
    return content[-1]
