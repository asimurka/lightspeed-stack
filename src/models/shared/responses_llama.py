"""Shared aliases for Llama Responses API input and include types."""

from typing import Literal

from llama_stack_api.openai_responses import (
    OpenAIResponseInputFunctionToolCallOutput as FunctionToolCallOutput,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseMCPApprovalRequest as McpApprovalRequest,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseMCPApprovalResponse as McpApprovalResponse,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseMessage as ResponseMessage,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageFileSearchToolCall as FileSearchToolCall,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageFunctionToolCall as FunctionToolCall,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageMCPCall as McpCall,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageMCPListTools as McpListTools,
)
from llama_stack_api.openai_responses import (
    OpenAIResponseOutputMessageWebSearchToolCall as WebSearchToolCall,
)

type IncludeParameter = Literal[
    "web_search_call.action.sources",
    "code_interpreter_call.outputs",
    "computer_call_output.output.image_url",
    "file_search_call.results",
    "message.input_image.image_url",
    "message.output_text.logprobs",
    "reasoning.encrypted_content",
]

type ResponseItem = (
    ResponseMessage
    | WebSearchToolCall
    | FileSearchToolCall
    | FunctionToolCallOutput
    | McpCall
    | McpListTools
    | McpApprovalRequest
    | FunctionToolCall
    | McpApprovalResponse
)

type ResponseInput = str | list[ResponseItem]

__all__ = ["IncludeParameter", "ResponseInput", "ResponseItem"]
