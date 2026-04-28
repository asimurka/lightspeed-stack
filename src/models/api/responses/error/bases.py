"""Base models for structured API error responses."""

from typing import Any, Optional

from pydantic import BaseModel, Field
from pydantic_core import SchemaError


class DetailModel(BaseModel):
    """Nested detail model for error responses."""

    response: str = Field(..., description="Short summary of the error")
    cause: str = Field(..., description="Detailed explanation of what caused the error")


class AbstractErrorResponse(BaseModel):
    """
    Base class for error responses.

    Attributes:
        status_code (int): HTTP status code for the error response.
        detail (DetailModel): The detail model containing error summary and cause.
    """

    status_code: int = Field(
        ..., description="HTTP status code for the errors response"
    )
    detail: DetailModel = Field(
        ..., description="The detail model containing error summary and cause"
    )

    def __init__(self, *, response: str, cause: str, status_code: int):
        """
        Create an error response model with an HTTP status code and detailed message.

        Parameters:
        ----------
            response (str): A short, user-facing summary of the error.
            cause (str): A more detailed explanation of the error cause.
            status_code (int): The HTTP status code to associate with this error response.
        """
        super().__init__(
            status_code=status_code, detail=DetailModel(response=response, cause=cause)
        )

    @classmethod
    def get_description(cls) -> str:
        """
        Retrieve the class description.

        Returns:
            str: The class `description` attribute if present; otherwise the
                 class docstring; if neither is present, an empty string.
        """
        return getattr(cls, "description", cls.__doc__ or "")

    @classmethod
    def openapi_response(cls, examples: Optional[list[str]] = None) -> dict[str, Any]:
        """
        Build an OpenAPI/FastAPI response dictionary that exposes the model's labeled examples.

        Extracts examples from the model's JSON schema and includes them as
        named application/json examples in the returned response mapping. If
        the optional `examples` list is provided, only examples whose labels
        appear in that list are included. Each included example is exposed
        under its label with a `value` containing a `detail` payload.

        Parameters:
        ----------
            examples (Optional[list[str]]): If provided, restricts which
                                            labeled examples to include by label.

        Returns:
        -------
            dict[str, Any]: A response mapping with keys:
                - "description": the response description,
                - "model": the model class,
                - "content": a mapping for "application/json" to the examples
                             object (or None if no examples).

        Raises:
        ------
            SchemaError: If any example in the model schema lacks a `label`.
        """
        schema = cls.model_json_schema()
        model_examples = schema.get("examples", [])

        named_examples: dict[str, Any] = {}
        for ex in model_examples:
            label = ex.get("label", None)
            if label is None:
                raise SchemaError(f"Example {ex} in {cls.__name__} has no label")
            if examples is None or label in examples:
                detail = ex.get("detail")
                if detail is not None:
                    named_examples[label] = {"value": {"detail": detail}}

        content: dict[str, Any] = {
            "application/json": {"examples": named_examples or None}
        }

        return {
            "description": cls.get_description(),
            "model": cls,
            "content": content,
        }
