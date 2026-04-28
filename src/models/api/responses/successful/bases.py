"""Base response models shared across API responses."""

from typing import Any

from pydantic import BaseModel
from pydantic_core import SchemaError

from models.api.responses.constants import SUCCESSFUL_RESPONSE_DESCRIPTION


class AbstractSuccessfulResponse(BaseModel):
    """Base class for all successful response models."""

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """Generate FastAPI response dict with a single example from model_config."""
        schema = cls.model_json_schema()
        model_examples = schema.get("examples")
        if not model_examples:
            raise SchemaError(f"Examples not found in {cls.__name__}")
        example_value = model_examples[0]
        content = {"application/json": {"example": example_value}}

        return {
            "description": SUCCESSFUL_RESPONSE_DESCRIPTION,
            "model": cls,
            "content": content,
        }


__all__ = ["AbstractSuccessfulResponse"]
