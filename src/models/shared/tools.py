"""Shared tool call/result summary models."""

from typing import Any

from pydantic import BaseModel, Field


class ToolCallSummary(BaseModel):
    """Model representing a tool call made during response generation (for tool_calls list)."""

    id: str = Field(description="ID of the tool call")
    name: str = Field(description="Name of the tool called")
    args: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool"
    )
    type: str = Field("tool_call", description="Type indicator for tool call")


class ToolResultSummary(BaseModel):
    """Model representing a result from a tool call (for tool_results list)."""

    id: str = Field(
        description="ID of the tool call/result, matches the corresponding tool call 'id'"
    )
    status: str = Field(
        ..., description="Status of the tool execution (e.g., 'success')"
    )
    content: str = Field(..., description="Content/result returned from the tool")
    type: str = Field("tool_result", description="Type indicator for tool result")
    round: int = Field(..., description="Round number or step of tool execution")


__all__ = ["ToolCallSummary", "ToolResultSummary"]
