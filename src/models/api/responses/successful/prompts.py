# pylint: disable=too-many-lines

"""Models for REST API responses."""

from typing import Any, Optional

from pydantic import Field
from pydantic_core import SchemaError

from models.api.responses.constants import (
    SUCCESSFUL_RESPONSE_DESCRIPTION,
)
from models.api.responses.successful.bases import AbstractSuccessfulResponse


class PromptResourceResponse(AbstractSuccessfulResponse):
    """A stored prompt template as returned by Llama Stack."""

    prompt_id: str = Field(..., description="Prompt identifier from Llama Stack")
    version: int = Field(..., description="Version number for this prompt")
    is_default: Optional[bool] = Field(
        None, description="Whether this version is the default"
    )
    prompt: Optional[str] = Field(None, description="Prompt text with placeholders")
    variables: Optional[list[str]] = Field(
        None, description="Variable names used in the template"
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "prompt_id": "pmpt_0123456789abcdef0123456789abcdef01234567",
                    "version": 1,
                    "is_default": True,
                    "prompt": "Summarize: {{text}}",
                    "variables": ["text"],
                }
            ]
        },
    }


class PromptsListResponse(AbstractSuccessfulResponse):
    """List of stored prompt templates returned by Llama Stack."""

    data: list[PromptResourceResponse] = Field(
        default_factory=list,
        description="Prompt entries (as returned by Llama Stack list)",
    )

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "data": [
                        {
                            "prompt_id": "pmpt_0123456789abcdef0123456789abcdef01234567",
                            "version": 1,
                            "is_default": True,
                            "prompt": "Summarize: {{text}}",
                            "variables": ["text"],
                        }
                    ],
                }
            ]
        },
    }


class PromptDeleteResponse(AbstractSuccessfulResponse):
    """Result of deleting a stored prompt (always HTTP 200, like conversations v2)."""

    prompt_id: str = Field(
        ...,
        description="Prompt identifier that was passed to delete.",
        examples=["pmpt_0123456789abcdef0123456789abcdef01234567"],
    )
    success: bool = Field(
        ...,
        description="Whether Llama Stack deleted the prompt.",
        examples=[True, False],
    )
    response: str = Field(
        ...,
        description="Human-readable outcome.",
        examples=[
            "Prompt deleted successfully",
            "Prompt cannot be deleted",
        ],
    )

    def __init__(self, *, deleted: bool, prompt_id: str) -> None:
        """Build delete outcome from Llama Stack result.

        Parameters:
            deleted: True if the backend removed the prompt.
            prompt_id: Prompt id from the request path.
        """
        response_msg = (
            "Prompt deleted successfully" if deleted else "Prompt cannot be deleted"
        )
        super().__init__(
            prompt_id=prompt_id,  # type: ignore[call-arg]
            success=deleted,  # type: ignore[call-arg]
            response=response_msg,  # type: ignore[call-arg]
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "deleted",
                    "value": {
                        "prompt_id": "pmpt_0123456789abcdef0123456789abcdef01234567",
                        "success": True,
                        "response": "Prompt deleted successfully",
                    },
                },
                {
                    "label": "not_deleted",
                    "value": {
                        "prompt_id": "pmpt_0123456789abcdef0123456789abcdef01234567",
                        "success": False,
                        "response": "Prompt cannot be deleted",
                    },
                },
            ]
        }
    }

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """Build the response spec for HTTP 200 with labeled JSON examples."""
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
