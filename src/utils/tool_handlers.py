"""Registry and atomic builders for Responses API ``output_item`` tool summaries."""

import json
from collections.abc import Callable
from typing import Any, Optional, cast

from llama_stack_api import (
    OpenAIResponseInputFunctionToolCallOutput as FunctionToolCallOutput,
    OpenAIResponseOutputMessageFileSearchToolCall as FileSearchCall,
    OpenAIResponseOutputMessageFunctionToolCall as FunctionCall,
    OpenAIResponseOutputMessageMCPCall as MCPCall,
    OpenAIResponseOutputMessageMCPListTools as MCPListTools,
    OpenAIResponseMCPApprovalRequest as MCPApprovalRequest,
    OpenAIResponseMCPApprovalResponse as MCPApprovalResponse,
    OpenAIResponseOutputMessageWebSearchToolCall as WebSearchCall,
)

from constants import DEFAULT_RAG_TOOL
from utils.types import ResponseItem, ToolCallSummary, ToolResultSummary

# ---------------------------------------------------------------------------
# function_call
# ---------------------------------------------------------------------------


def build_function_call_tool_call(item: FunctionCall) -> ToolCallSummary:
    """Build ``ToolCallSummary`` for a ``function_call`` output item."""
    return ToolCallSummary(
        id=item.call_id,
        name=item.name,
        args=parse_arguments_string(item.arguments),
        type="function_call",
    )


# ---------------------------------------------------------------------------
# function_call_output
# ---------------------------------------------------------------------------


def build_function_call_output_tool_result(
    item: FunctionToolCallOutput,
) -> ToolResultSummary:
    """Build ``ToolResultSummary`` for a ``function_call_output`` output item."""
    return ToolResultSummary(
        id=item.call_id,
        status=item.status or "success",
        content=item.output,
        type="function_call_output",
        round=1,
    )


def parse_arguments_string(arguments_str: str) -> dict[str, Any]:
    """Parse an arguments string into a dictionary.

    Args:
        arguments_str: The arguments string to parse

    Returns:
        Parsed dictionary if successful, otherwise {"args": arguments_str}
    """
    # Try parsing as-is first (most common case)
    try:
        parsed = json.loads(arguments_str)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Try wrapping in {} if string doesn't start with {
    # This handles cases where the string is just the content without braces
    stripped = arguments_str.strip()
    if stripped and not stripped.startswith("{"):
        try:
            wrapped = "{" + stripped + "}"
            parsed = json.loads(wrapped)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: return wrapped in arguments key
    return {"args": arguments_str}


# ---------------------------------------------------------------------------
# file_search_call
# ---------------------------------------------------------------------------


def file_search_results_payload(item: FileSearchCall) -> Optional[dict[str, Any]]:
    """Structured payload for the file_search tool result content, if any."""
    if item.results is None:
        return None
    return {"results": [result.model_dump() for result in item.results]}


def build_file_search_tool_call(item: FileSearchCall) -> ToolCallSummary:
    """Build ``ToolCallSummary`` for a ``file_search_call`` output item."""
    return ToolCallSummary(
        id=item.id,
        name=DEFAULT_RAG_TOOL,
        args={"queries": item.queries},
        type="file_search_call",
    )


def build_file_search_tool_result(item: FileSearchCall) -> ToolResultSummary:
    """Build ``ToolResultSummary`` for a ``file_search_call`` output item."""
    payload = file_search_results_payload(item)
    return ToolResultSummary(
        id=item.id,
        status=item.status,
        content=json.dumps(payload) if payload else "",
        type="file_search_call",
        round=1,
    )


# ---------------------------------------------------------------------------
# web_search_call
# ---------------------------------------------------------------------------


def build_web_search_tool_call(item: WebSearchCall) -> ToolCallSummary:
    """Build ``ToolCallSummary`` for a ``web_search_call`` output item."""
    return ToolCallSummary(
        id=item.id,
        name="web_search",
        args={},
        type="web_search_call",
    )


def build_web_search_tool_result(item: WebSearchCall) -> ToolResultSummary:
    """Build ``ToolResultSummary`` for a ``web_search_call`` output item."""
    return ToolResultSummary(
        id=item.id,
        status=item.status,
        content="",
        type="web_search_call",
        round=1,
    )


# ---------------------------------------------------------------------------
# mcp_call (output item done path — full MCP call object)
# ---------------------------------------------------------------------------


def build_mcp_output_tool_call(item: MCPCall) -> ToolCallSummary:
    """Build ``ToolCallSummary`` from a completed ``mcp_call`` output item."""
    args = parse_arguments_string(item.arguments)
    if item.server_label:
        args["server_label"] = item.server_label
    return ToolCallSummary(
        id=item.id,
        name=item.name,
        args=args,
        type="mcp_call",
    )


def build_mcp_output_tool_result(item: MCPCall) -> ToolResultSummary:
    """Build ``ToolResultSummary`` from a completed ``mcp_call`` output item."""
    content = item.error if item.error else (item.output if item.output else "")
    return ToolResultSummary(
        id=item.id,
        status="success" if item.error is None else "failure",
        content=content,
        type="mcp_call",
        round=1,
    )


def build_mcp_tool_call_from_arguments_done(
    item_info: tuple[str, str],
    arguments: str,
) -> ToolCallSummary:
    """Build ToolCallSummary from MCP call arguments completion event.

    Args:
        item_info: The item ID and name of the MCP call item
        arguments: The JSON string of arguments from the arguments.done event

    Returns:
        ToolCallSummary for the MCP call
    """
    item_id, item_name = item_info
    args = parse_arguments_string(arguments)
    return ToolCallSummary(
        id=item_id,
        name=item_name,
        args=args,
        type="mcp_call",
    )


# ---------------------------------------------------------------------------
# mcp_list_tools
# ---------------------------------------------------------------------------


def build_mcp_list_tools_tool_call(item: MCPListTools) -> ToolCallSummary:
    """Build ``ToolCallSummary`` for an ``mcp_list_tools`` output item."""
    return ToolCallSummary(
        id=item.id,
        name="mcp_list_tools",
        args={"server_label": item.server_label},
        type="mcp_list_tools",
    )


def build_mcp_list_tools_tool_result(item: MCPListTools) -> ToolResultSummary:
    """Build ``ToolResultSummary`` for an ``mcp_list_tools`` output item."""
    tools_info = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in item.tools
    ]
    content_dict = {
        "server_label": item.server_label,
        "tools": tools_info,
    }
    return ToolResultSummary(
        id=item.id,
        status="success",
        content=json.dumps(content_dict),
        type="mcp_list_tools",
        round=1,
    )


# ---------------------------------------------------------------------------
# mcp_approval_request / mcp_approval_response
# ---------------------------------------------------------------------------


def build_mcp_approval_request_tool_call(item: MCPApprovalRequest) -> ToolCallSummary:
    """Build ``ToolCallSummary`` for an ``mcp_approval_request`` output item."""
    return ToolCallSummary(
        id=item.id,
        name=item.name,
        args=parse_arguments_string(item.arguments),
        type="mcp_approval_request",
    )


def build_mcp_approval_response_tool_result(
    item: MCPApprovalResponse,
) -> ToolResultSummary:
    """Build ``ToolResultSummary`` for an ``mcp_approval_response`` output item."""
    content_dict: dict[str, Any] = {}
    if item.reason:
        content_dict["reason"] = item.reason
    return ToolResultSummary(
        id=item.approval_request_id,
        status="success" if item.approve else "denied",
        content=json.dumps(content_dict),
        type="mcp_approval_response",
        round=1,
    )


# ---------------------------------------------------------------------------
# Registries: ``output_item.type`` → builder (streaming + ``dispatch_output_item``)
# ---------------------------------------------------------------------------

ToolCallBuilderFn = Callable[[ResponseItem], Optional[ToolCallSummary]]
ToolResultBuilderFn = Callable[[ResponseItem], Optional[ToolResultSummary]]


def _tc_function_call(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_function_call_tool_call(cast(FunctionCall, output_item))


def _tr_function_call_output(
    output_item: ResponseItem,
) -> Optional[ToolResultSummary]:
    return build_function_call_output_tool_result(
        cast(FunctionToolCallOutput, output_item)
    )


def _tc_file_search(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_file_search_tool_call(cast(FileSearchCall, output_item))


def _tr_file_search(output_item: ResponseItem) -> Optional[ToolResultSummary]:
    return build_file_search_tool_result(cast(FileSearchCall, output_item))


def _tc_web_search(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_web_search_tool_call(cast(WebSearchCall, output_item))


def _tr_web_search(output_item: ResponseItem) -> Optional[ToolResultSummary]:
    return build_web_search_tool_result(cast(WebSearchCall, output_item))


def _tc_mcp_call(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_mcp_output_tool_call(cast(MCPCall, output_item))


def _tr_mcp_call(output_item: ResponseItem) -> Optional[ToolResultSummary]:
    return build_mcp_output_tool_result(cast(MCPCall, output_item))


def _tc_mcp_list_tools(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_mcp_list_tools_tool_call(cast(MCPListTools, output_item))


def _tr_mcp_list_tools(output_item: ResponseItem) -> Optional[ToolResultSummary]:
    return build_mcp_list_tools_tool_result(cast(MCPListTools, output_item))


def _tc_mcp_approval_request(output_item: ResponseItem) -> Optional[ToolCallSummary]:
    return build_mcp_approval_request_tool_call(cast(MCPApprovalRequest, output_item))


def _tr_mcp_approval_response(
    output_item: ResponseItem,
) -> Optional[ToolResultSummary]:
    return build_mcp_approval_response_tool_result(
        cast(MCPApprovalResponse, output_item)
    )


TOOL_CALL_BUILDERS: dict[str, ToolCallBuilderFn] = {
    "function_call": _tc_function_call,
    "file_search_call": _tc_file_search,
    "web_search_call": _tc_web_search,
    "mcp_call": _tc_mcp_call,
    "mcp_list_tools": _tc_mcp_list_tools,
    "mcp_approval_request": _tc_mcp_approval_request,
}

TOOL_RESULT_BUILDERS: dict[str, ToolResultBuilderFn] = {
    "function_call_output": _tr_function_call_output,
    "file_search_call": _tr_file_search,
    "web_search_call": _tr_web_search,
    "mcp_call": _tr_mcp_call,
    "mcp_list_tools": _tr_mcp_list_tools,
    "mcp_approval_response": _tr_mcp_approval_response,
}


def dispatch_response_item(
    item: ResponseItem,
) -> tuple[Optional[ToolCallSummary], Optional[ToolResultSummary]]:
    """Map ``output_item.type`` to tool call/result builders and return summaries."""
    tc = TOOL_CALL_BUILDERS.get(item.type)
    tr = TOOL_RESULT_BUILDERS.get(item.type)
    return (
        tc(item) if tc else None,
        tr(item) if tr else None,
    )
