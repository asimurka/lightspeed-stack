"""In-flight handles for items being built on the live response envelope."""

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
    tool_arguments_dict,
)

OpenTool = FunctionToolCall | McpCall | FileSearchToolCall


@dataclass
class ItemTracker:
    """Track open output items by mutating objects already on response.output."""

    open_message: Optional[ResponseMessage] = None
    open_reasoning: Optional[ReasoningItem] = None
    open_tools: dict[str, OpenTool] = field(default_factory=dict)
    last_tool_call_id: Optional[str] = None
    unclosed_tool_args: set[str] = field(default_factory=set)
    hidden_output_indices: set[int] = field(default_factory=set)
    lifecycle_started: bool = False

    def get_open_tool(self, tool_call_id: str) -> Optional[OpenTool]:
        """Look up an in-flight tool output item.

        Args:
            tool_call_id: Call id registered in open_tools.

        Returns:
            The open tool item, or None if the call is not tracked.

        """
        return self.open_tools.get(tool_call_id)

    def close_tool(self, tool_call_id: str) -> None:
        """Remove a tool from open_tools after its output item is finished.

        Args:
            tool_call_id: Call id to drop from the tracker.

        """
        self.open_tools.pop(tool_call_id, None)
        self.unclosed_tool_args.discard(tool_call_id)

    def extend_open_message(self, chunk: str) -> None:
        """Append streamed text to the open assistant message.

        Args:
            chunk: Text delta for the current output_text part.

        """
        message = self.open_message
        if message is None:
            return
        part = open_message_part(message)
        if part is None:
            return
        part.text += chunk

    def extend_open_reasoning(self, chunk: str) -> None:
        """Append streamed text to the open reasoning item.

        Args:
            chunk: Text delta for the current reasoning_text part.

        """
        reasoning = self.open_reasoning
        if reasoning is None:
            return
        part = open_reasoning_part(reasoning)
        if part is None:
            return
        part.text += chunk

    def extend_open_tool_args(
        self,
        tool_call_id: str,
        args: str | dict[str, Any] | None,
        *,
        replace: bool = False,
    ) -> Optional[OpenTool]:
        """Update the open tool item for a single argument event.

        File search ignores streamed args: OpenResponses has no argument-delta
        events for file_search_call, so queries are set only on replace.

        Args:
            tool_call_id: Call id used when the tool was registered in open_tools.
            args: None is a no-op. A string concatenates the next JSON fragment.
                A dict merges fields into the arguments built so far.
            replace: When True, set arguments from args instead of appending or merging.

        Returns:
            The open item after applying args, or None if the call id is unknown.

        """
        item = self.get_open_tool(tool_call_id)
        if item is None:
            return None
        if args is None:
            return item
        if isinstance(item, FileSearchToolCall):
            if not replace:
                return item
            if queries := file_search_queries(tool_arguments_dict(args)):
                item.queries = queries
            return item
        if replace:
            item.arguments = arguments_json(args)
        elif isinstance(args, str):
            item.arguments += args
        else:  # isinstance(args, dict)
            item.arguments = merge_argument_delta(item.arguments, args)
        return item


def open_message_part(item: ResponseMessage) -> Optional[OutputTextPart]:
    """Return the trailing output_text part when the message is still streaming.

    Args:
        item: Open assistant message on the response.

    Returns:
        The last output_text part, or None when content is not streaming-shaped.

    """
    content = item.content
    if isinstance(content, str) or not content:
        return None
    part = content[-1]
    return part if isinstance(part, OutputTextPart) else None


def open_reasoning_part(item: ReasoningItem) -> Optional[ReasoningContent]:
    """Return the trailing reasoning content part on an open reasoning item.

    Args:
        item: Open reasoning item on the response.

    Returns:
        The last reasoning content part, or None when content is empty.

    """
    content = item.content
    if not content:
        return None
    return content[-1]
