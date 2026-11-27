"""Serialize tool arguments, usage, and ids for OpenResponses output."""

from __future__ import annotations

import json
from typing import Any

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


def streamed_arguments_delta(
    previous: str,
    current: str,
    *,
    keep_object_open: bool = False,
) -> str:
    """Return the concatenable JSON suffix from previous to current arguments.

    OpenResponses argument deltas are concatenated. An empty object on the item
    is treated as nothing streamed yet. Dict-shaped PAI deltas keep the object
    unclosed so later keys can append; the closing brace is emitted on done.
    If current is not an extension of previous, return empty.

    Args:
        previous: Arguments JSON on the item before this event.
        current: Arguments JSON on the item after this event.
        keep_object_open: Strip a trailing object brace so new keys can append.

    Returns:
        Text to emit as function_call or mcp_call arguments.delta.

    """
    if keep_object_open:
        previous = _unclosed_object_json(previous)
        current = _unclosed_object_json(current)
    baseline = "" if previous in ("", "{}") else previous
    if current.startswith(baseline):
        return current[len(baseline) :]
    return ""


def _unclosed_object_json(arguments: str) -> str:
    """Drop a trailing object brace so argument JSON can still grow.

    Args:
        arguments: Complete or partial arguments JSON.

    Returns:
        arguments without a final }, or empty when nothing has been streamed.

    """
    if arguments in ("", "{}"):
        return ""
    if arguments.endswith("}"):
        return arguments[:-1]
    return arguments


def merge_argument_delta(existing: str, delta: dict[str, Any]) -> str:
    """Shallow-merge a dict argument delta onto accumulated JSON arguments.

    Args:
        existing: Current ``arguments`` JSON string.
        delta: Dict-shaped tool argument delta from Pydantic AI.

    Returns:
        JSON object text after the merge.

    """
    return json.dumps({**parse_arguments(existing), **delta})


def tool_arguments_dict(args: str | dict[str, Any] | None) -> dict[str, Any]:
    """Normalize raw tool arguments to a parsed object.

    Args:
        args: Final or partial arguments from the agent.

    Returns:
        A dict suitable for reading fields; empty when missing or invalid.

    """
    if args is None:
        return {}
    if isinstance(args, dict):
        return args
    return parse_arguments(args)


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
