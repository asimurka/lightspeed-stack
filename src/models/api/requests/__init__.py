"""REST API request models split by endpoint family."""

from models.api.requests.catalog import ModelFilter
from models.api.requests.conversations import ConversationUpdateRequest
from models.api.requests.feedback import (
    FeedbackCategory,
    FeedbackRequest,
    FeedbackStatusUpdateRequest,
)
from models.api.requests.mcp_servers import MCPServerRegistrationRequest
from models.api.requests.prompts import PromptCreateRequest, PromptUpdateRequest
from models.api.requests.query import Attachment, QueryRequest, SolrVectorSearchRequest
from models.api.requests.responses_openai import ResponsesRequest
from models.api.requests.rlsapi import (
    RlsapiV1Attachment,
    RlsapiV1CLA,
    RlsapiV1Context,
    RlsapiV1InferRequest,
    RlsapiV1SystemInfo,
    RlsapiV1Terminal,
)
from models.api.requests.streaming_interrupt import StreamingInterruptRequest
from models.api.requests.vector_stores import (
    VectorStoreCreateRequest,
    VectorStoreFileCreateRequest,
    VectorStoreUpdateRequest,
)

__all__ = [
    "Attachment",
    "SolrVectorSearchRequest",
    "QueryRequest",
    "StreamingInterruptRequest",
    "FeedbackCategory",
    "FeedbackRequest",
    "FeedbackStatusUpdateRequest",
    "ConversationUpdateRequest",
    "ModelFilter",
    "ResponsesRequest",
    "MCPServerRegistrationRequest",
    "VectorStoreCreateRequest",
    "VectorStoreUpdateRequest",
    "VectorStoreFileCreateRequest",
    "PromptCreateRequest",
    "PromptUpdateRequest",
    "RlsapiV1Attachment",
    "RlsapiV1Terminal",
    "RlsapiV1SystemInfo",
    "RlsapiV1CLA",
    "RlsapiV1Context",
    "RlsapiV1InferRequest",
]
