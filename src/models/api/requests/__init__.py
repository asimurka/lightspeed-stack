"""Concrete REST API request models grouped by domain."""

from models.api.requests.catalog import ModelFilter
from models.api.requests.conversations import ConversationUpdateRequest
from models.api.requests.feedback import FeedbackRequest, FeedbackStatusUpdateRequest
from models.api.requests.mcp_servers import MCPServerRegistrationRequest
from models.api.requests.prompts import PromptCreateRequest, PromptUpdateRequest
from models.api.requests.query import QueryRequest, StreamingInterruptRequest
from models.api.requests.responses_openai import ResponsesRequest
from models.api.requests.vector_stores import (
    VectorStoreCreateRequest,
    VectorStoreFileCreateRequest,
    VectorStoreUpdateRequest,
)

__all__ = [
    "ConversationUpdateRequest",
    "FeedbackRequest",
    "FeedbackStatusUpdateRequest",
    "MCPServerRegistrationRequest",
    "ModelFilter",
    "PromptCreateRequest",
    "PromptUpdateRequest",
    "QueryRequest",
    "ResponsesRequest",
    "StreamingInterruptRequest",
    "VectorStoreCreateRequest",
    "VectorStoreFileCreateRequest",
    "VectorStoreUpdateRequest",
]
