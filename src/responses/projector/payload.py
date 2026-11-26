"""Serialize tool arguments, usage, and ids for OpenResponses output."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic_ai.messages import RetryPromptPart, ToolReturnPart
from pydantic_ai.usage import RunUsage

from responses.models.config import (
    ResponseUsage,
    UsageInputTokensDetails,
    UsageOutputTokensDetails,
)


def arguments_json(args: str | dict[str, Any] | None) -> str:
    """Serialize tool arguments as JSON text.

    Args:
        args: Raw tool arguments from the agent.

    Returns:
        JSON object text, or an empty object when arguments are missing.

    """
    if args is None:
        return "{}"
    if isinstance(args, str):
        return args
    return json.dumps(args)


def arguments_delta_text(args_delta: str | dict[str, Any] | None) -> str:
    """Normalize a streamed arguments fragment to text.

    Args:
        args_delta: Incremental tool arguments from the agent.

    Returns:
        Text to append or replace on the open tool item.

    """
    if args_delta is None:
        return ""
    if isinstance(args_delta, str):
        return args_delta
    return json.dumps(args_delta)


def merge_argument_delta(existing: str, delta: dict[str, Any]) -> str:
    """Shallow-merge a dict argument delta onto accumulated JSON arguments.

    Args:
        existing: Current ``arguments`` JSON string.
        delta: Dict-shaped tool argument delta from Pydantic AI.

    Returns:
        JSON object text after the merge.

    """
    return json.dumps({**parse_arguments(existing), **delta})


def parse_arguments(arguments: str) -> dict[str, Any]:
    """Parse accumulated tool arguments JSON.

    Args:
        arguments: JSON arguments string.

    Returns:
        Parsed object, or an empty dict when parsing fails.

    """
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def mcp_tool_name(tool_name: str, _server_label: Optional[str]) -> str:
    """Strip the PAI mcp_ prefix for the mcp_call item name.

    Args:
        tool_name: Tool name from the agent.
        _server_label: Reserved; server label is on the item, not in the name.

    Returns:
        Bare MCP tool name for the output item.

    """
    return tool_name.removeprefix("mcp_")


def tool_failed(part: ToolReturnPart | RetryPromptPart) -> bool:
    """Return whether a tool result should count as a failure.

    Args:
        part: Tool return or retry prompt from the agent.

    Returns:
        True when the call failed, was denied, or was interrupted.

    """
    if isinstance(part, RetryPromptPart):
        return True
    return part.outcome in {"failed", "denied", "interrupted"}


def return_text(part: ToolReturnPart | RetryPromptPart) -> str:
    """Text for MCP output or error fields on a completed call.

    Args:
        part: Tool return or retry prompt from the agent.

    Returns:
        String suitable for MCP call output or error.

    """
    if isinstance(part, RetryPromptPart):
        return str(part.content)
    return part.model_response_str()


def usage_from_run(usage: RunUsage) -> ResponseUsage:
    """Map agent token usage to the OpenResponses usage object.

    Args:
        usage: Usage totals from the agent run.

    Returns:
        Usage block for the response envelope.

    """
    return ResponseUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        input_tokens_details=UsageInputTokensDetails(
            cached_tokens=usage.cache_read_tokens
        ),
        output_tokens_details=UsageOutputTokensDetails(
            reasoning_tokens=usage.details.get("reasoning_tokens", 0)
        ),
    )
