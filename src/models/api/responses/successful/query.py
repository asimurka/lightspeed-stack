# pylint: disable=too-many-lines

"""Models for REST API responses."""

from typing import Optional

from pydantic import BaseModel, Field

from models.api.responses.successful.bases import AbstractSuccessfulResponse
from models.shared.rag import RAGChunk, ReferencedDocument
from models.shared.tools import ToolCallSummary, ToolResultSummary


class ConversationData(BaseModel):
    """Model representing conversation data returned by cache list operations.

    Attributes:
        conversation_id: The conversation ID
        topic_summary: The topic summary for the conversation (can be None)
        last_message_timestamp: The timestamp of the last message in the conversation
    """

    conversation_id: str
    topic_summary: Optional[str]
    last_message_timestamp: float


class QueryResponse(AbstractSuccessfulResponse):
    """Model representing LLM response to a query.

    Attributes:
        conversation_id: The optional conversation ID (UUID).
        response: The response.
        rag_chunks: Deprecated. List of RAG chunks used to generate the response.
            This information is now available in tool_results under file_search_call type.
        referenced_documents: The URLs and titles for the documents used to generate the response.
        tool_calls: List of tool calls made during response generation.
        tool_results: List of tool results.
        truncated: Whether conversation history was truncated.
        input_tokens: Number of tokens sent to LLM.
        output_tokens: Number of tokens received from LLM.
        available_quotas: Quota available as measured by all configured quota limiters.
    """

    conversation_id: Optional[str] = Field(
        None,
        description="The optional conversation ID (UUID)",
        examples=["c5260aec-4d82-4370-9fdf-05cf908b3f16"],
    )

    response: str = Field(
        description="Response from LLM",
        examples=[
            "Kubernetes is an open-source container orchestration system for automating ..."
        ],
    )

    rag_chunks: list[RAGChunk] = Field(
        default_factory=list,
        description="Deprecated: List of RAG chunks used to generate the response.",
    )

    referenced_documents: list[ReferencedDocument] = Field(
        default_factory=list,
        description="List of documents referenced in generating the response",
        examples=[
            [
                {
                    "doc_url": "https://docs.openshift.com/"
                    "container-platform/4.15/operators/olm/index.html",
                    "doc_title": "Operator Lifecycle Manager (OLM)",
                }
            ]
        ],
    )

    truncated: bool = Field(
        False,
        description="Deprecated:Whether conversation history was truncated",
        examples=[False, True],
    )

    input_tokens: int = Field(
        0,
        description="Number of tokens sent to LLM",
        examples=[150, 250, 500],
    )

    output_tokens: int = Field(
        0,
        description="Number of tokens received from LLM",
        examples=[50, 100, 200],
    )

    available_quotas: dict[str, int] = Field(
        default_factory=dict,
        description="Quota available as measured by all configured quota limiters",
        examples=[{"daily": 1000, "monthly": 50000}],
    )

    tool_calls: list[ToolCallSummary] = Field(
        default_factory=list,
        description="List of tool calls made during response generation",
    )

    tool_results: list[ToolResultSummary] = Field(
        default_factory=list,
        description="List of tool results",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "response": "Operator Lifecycle Manager (OLM) helps users install...",
                    "referenced_documents": [
                        {
                            "doc_url": "https://docs.openshift.com/container-platform/4.15/"
                            "operators/understanding/olm/olm-understanding-olm.html",
                            "doc_title": "Operator Lifecycle Manager concepts and resources",
                        },
                    ],
                    "truncated": False,
                    "input_tokens": 123,
                    "output_tokens": 456,
                    "available_quotas": {
                        "UserQuotaLimiter": 998911,
                        "ClusterQuotaLimiter": 998911,
                    },
                    "tool_calls": [
                        {"name": "tool1", "args": {}, "id": "1", "type": "tool_call"}
                    ],
                    "tool_results": [
                        {
                            "id": "1",
                            "status": "success",
                            "content": "bla",
                            "type": "tool_result",
                            "round": 1,
                        }
                    ],
                }
            ]
        }
    }
