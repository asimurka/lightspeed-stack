"""Shared model for prepared Llama Responses API request parameters."""

from typing import Any, Optional

from llama_stack_api.openai_responses import (
    OpenAIResponseInputTool as InputTool,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseInputToolChoice as ToolChoice,
)
from llama_stack_api.openai_responses import (
    OpenAIResponsePrompt as Prompt,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseReasoning as Reasoning,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseText as Text,
)
from pydantic import BaseModel, Field

from models.shared.responses_llama import IncludeParameter, ResponseInput


class ResponsesApiParams(BaseModel):
    """Parameters for a Llama Stack Responses API request.

    All fields accepted by the Llama Stack client responses.create() body are
    included so that dumped model can be passed directly to response create.
    """

    input: ResponseInput = Field(description="The input text or structured input items")
    model: str = Field(description='The full model ID in format "provider/model"')
    conversation: str = Field(description="The conversation ID in llama-stack format")
    include: Optional[list[IncludeParameter]] = Field(
        default=None,
        description="Output item types to include in the response",
    )
    instructions: Optional[str] = Field(
        default=None, description="The resolved system prompt"
    )
    max_infer_iters: Optional[int] = Field(
        default=None,
        description="Maximum number of inference iterations",
    )
    max_output_tokens: Optional[int] = Field(
        default=None,
        description="Maximum number of tokens allowed in the response",
    )
    max_tool_calls: Optional[int] = Field(
        default=None,
        description="Maximum tool calls allowed in a single response",
    )
    metadata: Optional[dict[str, str]] = Field(
        default=None,
        description="Custom metadata for tracking or logging",
    )
    parallel_tool_calls: Optional[bool] = Field(
        default=None,
        description="Whether the model can make multiple tool calls in parallel",
    )
    previous_response_id: Optional[str] = Field(
        default=None,
        description="Identifier of the previous response in a multi-turn conversation",
    )
    prompt: Optional[Prompt] = Field(
        default=None,
        description="Prompt template with variables for dynamic substitution",
    )
    reasoning: Optional[Reasoning] = Field(
        default=None,
        description="Reasoning configuration for the response",
    )
    safety_identifier: Optional[str] = Field(
        default=None,
        description="Stable identifier for safety monitoring and abuse detection",
    )
    store: bool = Field(description="Whether to store the response")
    stream: bool = Field(description="Whether to stream the response")
    temperature: Optional[float] = Field(
        default=None,
        description="Sampling temperature (e.g., 0.0-2.0)",
    )
    text: Optional[Text] = Field(
        default=None,
        description="Text response configuration (format constraints)",
    )
    tool_choice: Optional[ToolChoice] = Field(
        default=None,
        description="Tool selection strategy",
    )
    tools: Optional[list[InputTool]] = Field(
        default=None,
        description="Prepared tool groups for Responses API (same type as ResponsesRequest.tools)",
    )
    extra_headers: Optional[dict[str, str]] = Field(
        default=None,
        description="Extra HTTP headers to send with the request (e.g. x-llamastack-provider-data)",
    )

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Serialize params, re-injecting MCP authorization stripped by exclude=True.

        llama-stack-api marks ``InputToolMCP.authorization`` with
        ``Field(exclude=True)`` to prevent token leakage in API responses.
        The base ``model_dump()`` therefore strips the field, but we need it
        in the request payload so llama-stack server can authenticate with
        MCP servers.  See LCORE-1414 / GitHub issue #1269.
        """
        result = super().model_dump(*args, **kwargs)
        # Only one context option is allowed, previous_response_id has priority
        # Turn is added to conversation manually if previous_response_id is used
        if self.previous_response_id:
            result.pop("conversation", None)
        dumped_tools = result.get("tools")
        if not self.tools or not isinstance(dumped_tools, list):
            return result
        if len(dumped_tools) != len(self.tools):
            return result
        for tool, dumped_tool in zip(self.tools, dumped_tools):
            authorization = getattr(tool, "authorization", None)
            if authorization is not None and isinstance(dumped_tool, dict):
                dumped_tool["authorization"] = authorization
        return result


__all__ = ["ResponsesApiParams"]
