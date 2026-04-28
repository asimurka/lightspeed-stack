# pylint: disable=too-many-lines

"""Models for REST API responses."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_core import SchemaError

from models.api.responses.constants import (
    SUCCESSFUL_RESPONSE_DESCRIPTION,
)
from models.api.responses.successful.bases import AbstractSuccessfulResponse
from models.api.responses.successful.query import ConversationData
from models.shared.rag import ReferencedDocument
from models.shared.tools import ToolCallSummary, ToolResultSummary


class Message(BaseModel):
    """Model representing a message in a conversation turn.

    Attributes:
        content: The message content.
        type: The type of message.
        referenced_documents: Optional list of documents referenced in an assistant response.
    """

    content: str = Field(
        ...,
        description="The message content",
        examples=["Hello, how can I help you?"],
    )
    type: Literal["user", "assistant", "system", "developer"] = Field(
        ...,
        description="The type of message",
        examples=["user", "assistant", "system", "developer"],
    )
    referenced_documents: Optional[list[ReferencedDocument]] = Field(
        None,
        description="List of documents referenced in the response (assistant messages only)",
    )


class ConversationTurn(BaseModel):
    """Model representing a single conversation turn.

    Attributes:
        messages: List of messages in this turn.
        tool_calls: List of tool calls made in this turn.
        tool_results: List of tool results from this turn.
        provider: Provider identifier used for this turn.
        model: Model identifier used for this turn.
        started_at: ISO 8601 timestamp when the turn started.
        completed_at: ISO 8601 timestamp when the turn completed.
    """

    messages: list[Message] = Field(
        default_factory=list,
        description="List of messages in this turn",
    )
    tool_calls: list[ToolCallSummary] = Field(
        default_factory=list,
        description="List of tool calls made in this turn",
    )
    tool_results: list[ToolResultSummary] = Field(
        default_factory=list,
        description="List of tool results from this turn",
    )
    provider: str = Field(
        ...,
        description="Provider identifier used for this turn",
        examples=["openai"],
    )
    model: str = Field(
        ...,
        description="Model identifier used for this turn",
        examples=["gpt-4o-mini"],
    )
    started_at: str = Field(
        ...,
        description="ISO 8601 timestamp when the turn started",
        examples=["2024-01-01T00:01:00Z"],
    )
    completed_at: str = Field(
        ...,
        description="ISO 8601 timestamp when the turn completed",
        examples=["2024-01-01T00:01:05Z"],
    )


class ConversationResponse(AbstractSuccessfulResponse):
    """Model representing a response for retrieving a conversation.

    Attributes:
        conversation_id: The conversation ID (UUID).
        chat_history: The chat history as a list of conversation turns.
    """

    conversation_id: str = Field(
        ...,
        description="Conversation ID (UUID)",
        examples=["c5260aec-4d82-4370-9fdf-05cf908b3f16"],
    )

    chat_history: list[ConversationTurn] = Field(
        ...,
        description="The simplified chat history as a list of conversation turns",
        examples=[
            {
                "messages": [
                    {"content": "Hello", "type": "user"},
                    {"content": "Hi there!", "type": "assistant"},
                ],
                "tool_calls": [],
                "tool_results": [],
                "provider": "openai",
                "model": "gpt-4o-mini",
                "started_at": "2024-01-01T00:01:00Z",
                "completed_at": "2024-01-01T00:01:05Z",
            }
        ],
    )

    # provides examples for /docs endpoint
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "chat_history": [
                        {
                            "messages": [
                                {"content": "Hello", "type": "user"},
                                {"content": "Hi there!", "type": "assistant"},
                            ],
                            "tool_calls": [],
                            "tool_results": [],
                            "provider": "openai",
                            "model": "gpt-4o-mini",
                            "started_at": "2024-01-01T00:01:00Z",
                            "completed_at": "2024-01-01T00:01:05Z",
                        }
                    ],
                }
            ]
        }
    }


class ConversationDeleteResponse(AbstractSuccessfulResponse):
    """Model representing a response for deleting a conversation.

    Attributes:
        conversation_id: The conversation ID (UUID) that was deleted.
        success: Whether the deletion was successful.
        response: A message about the deletion result.
    """

    conversation_id: str = Field(
        ...,
        description="The conversation ID (UUID) that was deleted.",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    success: bool = Field(
        ..., description="Whether the deletion was successful.", examples=[True, False]
    )
    response: str = Field(
        ...,
        description="A message about the deletion result.",
        examples=[
            "Conversation deleted successfully",
            "Conversation cannot be deleted",
        ],
    )

    def __init__(self, *, deleted: bool, conversation_id: str) -> None:
        """
        Initialize a ConversationDeleteResponse and populate its public fields.

        If `deleted` is True the response message is "Conversation deleted
        successfully"; otherwise it is "Conversation cannot be deleted".

        Parameters:
        ----------
            deleted (bool): Whether the conversation was successfully deleted.
            conversation_id (str): The ID of the conversation.
        """
        response_msg = (
            "Conversation deleted successfully"
            if deleted
            else "Conversation cannot be deleted"
        )
        super().__init__(
            conversation_id=conversation_id,  # type: ignore[call-arg]
            success=True,  # type: ignore[call-arg]
            response=response_msg,  # type: ignore[call-arg]
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "deleted",
                    "value": {
                        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                        "success": True,
                        "response": "Conversation deleted successfully",
                    },
                },
                {
                    "label": "not found",
                    "value": {
                        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                        "success": True,
                        "response": "Conversation can not be deleted",
                    },
                },
            ]
        }
    }

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """
        Build an OpenAPI-compatible FastAPI response dict using the model's examples.

        Extracts labeled examples from the model's JSON schema `examples` and
        places them under `application/json` -> `examples`. The returned
        mapping includes a `description` ("Successful response"), the `model`
        (the class itself), and `content` containing the assembled examples.

        Returns:
            response (dict[str, Any]): A dict with keys `description`, `model`,
            and `content` suitable for FastAPI/OpenAPI response registration.

        Raises:
            SchemaError: If any example in the model's JSON schema is missing a
                         required `label` or `value`.
        """
        schema = cls.model_json_schema()
        model_examples = schema.get("examples", [])

        named_examples: dict[str, Any] = {}

        for ex in model_examples:
            label = ex.get("label")
            if label is None:
                raise SchemaError(f"Example {ex} in {cls.__name__} has no label")

            value = ex.get("value")
            if value is None:
                raise SchemaError(f"Example '{label}' in {cls.__name__} has no value")

            named_examples[label] = {"value": value}

        content = {"application/json": {"examples": named_examples or None}}

        return {
            "description": SUCCESSFUL_RESPONSE_DESCRIPTION,
            "model": cls,
            "content": content,
        }


class ConversationDetails(BaseModel):
    """Model representing the details of a user conversation.

    Attributes:
        conversation_id: The conversation ID (UUID).
        created_at: When the conversation was created.
        last_message_at: When the last message was sent.
        message_count: Number of user messages in the conversation.
        last_used_model: The last model used for the conversation.
        last_used_provider: The provider of the last used model.
        topic_summary: The topic summary for the conversation.

    Example:
        ```python
        conversation = ConversationDetails(
            conversation_id="123e4567-e89b-12d3-a456-426614174000",
            created_at="2024-01-01T00:00:00Z",
            last_message_at="2024-01-01T00:05:00Z",
            message_count=5,
            last_used_model="gemini/gemini-2.0-flash",
            last_used_provider="gemini",
            topic_summary="Openshift Microservices Deployment Strategies",
        )
        ```
    """

    conversation_id: str = Field(
        ...,
        description="Conversation ID (UUID)",
        examples=["c5260aec-4d82-4370-9fdf-05cf908b3f16"],
    )

    created_at: Optional[str] = Field(
        None,
        description="When the conversation was created",
        examples=["2024-01-01T01:00:00Z"],
    )

    last_message_at: Optional[str] = Field(
        None,
        description="When the last message was sent",
        examples=["2024-01-01T01:00:00Z"],
    )

    message_count: Optional[int] = Field(
        None,
        description="Number of user messages in the conversation",
        examples=[42],
    )

    last_used_model: Optional[str] = Field(
        None,
        description="Identification of the last model used for the conversation",
        examples=["gpt-4-turbo", "gpt-3.5-turbo-0125"],
    )

    last_used_provider: Optional[str] = Field(
        None,
        description="Identification of the last provider used for the conversation",
        examples=["openai", "gemini"],
    )

    topic_summary: Optional[str] = Field(
        None,
        description="Topic summary for the conversation",
        examples=["Openshift Microservices Deployment Strategies"],
    )


class ConversationsListResponse(AbstractSuccessfulResponse):
    """Model representing a response for listing conversations of a user.

    Attributes:
        conversations: List of conversation details associated with the user.
    """

    conversations: list[ConversationDetails]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversations": [
                        {
                            "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                            "created_at": "2024-01-01T00:00:00Z",
                            "last_message_at": "2024-01-01T00:05:00Z",
                            "message_count": 5,
                            "last_used_model": "gemini/gemini-2.0-flash",
                            "last_used_provider": "gemini",
                            "topic_summary": "Openshift Microservices Deployment Strategies",
                        },
                        {
                            "conversation_id": "456e7890-e12b-34d5-a678-901234567890",
                            "created_at": "2024-01-01T01:00:00Z",
                            "message_count": 2,
                            "last_used_model": "gemini/gemini-2.5-flash",
                            "last_used_provider": "gemini",
                            "topic_summary": "RHDH Purpose Summary",
                        },
                    ]
                }
            ]
        }
    }


class ConversationsListResponseV2(AbstractSuccessfulResponse):
    """Model representing a response for listing conversations of a user.

    Attributes:
        conversations: List of conversation data associated with the user.
    """

    conversations: list[ConversationData]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversations": [
                        {
                            "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                            "topic_summary": "Openshift Microservices Deployment Strategies",
                            "last_message_timestamp": 1704067200.0,
                        }
                    ],
                }
            ]
        }
    }


class ConversationUpdateResponse(AbstractSuccessfulResponse):
    """Model representing a response for updating a conversation topic summary.

    Attributes:
        conversation_id: The conversation ID (UUID) that was updated.
        success: Whether the update was successful.
        message: A message about the update result.

    Example:
        ```python
        update_response = ConversationUpdateResponse(
            conversation_id="123e4567-e89b-12d3-a456-426614174000",
            success=True,
            message="Topic summary updated successfully",
        )
        ```
    """

    conversation_id: str = Field(
        ...,
        description="The conversation ID (UUID) that was updated",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    success: bool = Field(
        ...,
        description="Whether the update was successful",
        examples=[True],
    )
    message: str = Field(
        ...,
        description="A message about the update result",
        examples=["Topic summary updated successfully"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                    "success": True,
                    "message": "Topic summary updated successfully",
                }
            ]
        }
    }
