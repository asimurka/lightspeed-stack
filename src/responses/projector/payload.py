"""Helpers for OpenResponses item ids, tool arguments, and usage mapping."""

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
from responses.models.items import ResponseOutput


def item_id(item: ResponseOutput) -> str:
    """Return the public id of an output item.

    Args:
        item: Projected OpenResponses output item.

    Returns:
        The item id, or the function-call id when no item id is set.

    """
    value = getattr(item, "id", None)
    if isinstance(value, str) and value:
        return value
    call_id = getattr(item, "call_id", None)
    return call_id if isinstance(call_id, str) else ""


def arguments_json(args: str | dict[str, Any] | None) -> str:
    """Serialize tool-call arguments as a JSON string.

    Args:
        args: Raw PAI tool-call arguments.

    Returns:
        JSON object text, or ``{}`` when arguments are missing.

    """
    if args is None:
        return "{}"
    if isinstance(args, str):
        return args
    return json.dumps(args)


def arguments_delta_text(args_delta: str | dict[str, Any] | None) -> str:
    """Normalize a tool-call arguments delta to a string.

    Args:
        args_delta: Incremental arguments from PAI.

    Returns:
        Text to append or replace on the open item.

    """
    if args_delta is None:
        return ""
    if isinstance(args_delta, str):
        return args_delta
    return json.dumps(args_delta)


def parse_arguments(arguments: str) -> dict[str, Any]:
    """Parse a JSON arguments string.

    Args:
        arguments: Accumulated tool-call arguments text.

    Returns:
        A dict, or empty when the text is not a JSON object.

    """
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def mcp_tool_name(tool_name: str, server_label: Optional[str]) -> str:
    """Strip a server-label prefix from an MCP tool name when present.

    Args:
        tool_name: PAI tool name.
        server_label: MCP server label for this call, if known.

    Returns:
        MCP tool name as it should appear on ``mcp_call``.

    """
    name = tool_name.removeprefix("mcp_") if tool_name.startswith("mcp_") else tool_name
    if server_label and name.startswith(f"{server_label}_"):
        return name.removeprefix(f"{server_label}_")
    return name


def tool_failed(part: ToolReturnPart | RetryPromptPart) -> bool:
    """Return whether a tool result should be projected as a failure.

    Args:
        part: Tool return or retry prompt from PAI.

    Returns:
        True when the call failed, was denied, or was interrupted.

    """
    if isinstance(part, RetryPromptPart):
        return True
    return part.outcome in {"failed", "denied", "interrupted"}


def return_text(part: ToolReturnPart | RetryPromptPart) -> str:
    """Stringify a tool return or retry prompt for MCP output or error.

    Args:
        part: Tool return or retry prompt from PAI.

    Returns:
        Text suitable for ``mcp_call.output`` or ``mcp_call.error``.

    """
    if isinstance(part, RetryPromptPart):
        return str(part.content)
    return part.model_response_str()


def usage_from_run(usage: RunUsage) -> ResponseUsage:
    """Map PAI run usage onto the OpenResponses usage object.

    Args:
        usage: Aggregated usage from the agent run.

    Returns:
        OpenResponses usage object.

    """
    reasoning_tokens = 0
    if usage.details:
        reasoning_tokens = int(usage.details.get("reasoning_tokens", 0) or 0)
    return ResponseUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.input_tokens + usage.output_tokens,
        input_tokens_details=UsageInputTokensDetails(
            cached_tokens=usage.cache_read_tokens
        ),
        output_tokens_details=UsageOutputTokensDetails(
            reasoning_tokens=reasoning_tokens
        ),
    )
