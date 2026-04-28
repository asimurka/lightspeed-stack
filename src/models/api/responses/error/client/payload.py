"""413/422/429 payload, validation, and quota error responses."""

from typing import ClassVar, Optional

from fastapi import status

from models.api.responses.constants import (
    PROMPT_TOO_LONG_DESCRIPTION,
    QUOTA_EXCEEDED_DESCRIPTION,
    UNPROCESSABLE_CONTENT_DESCRIPTION,
)
from models.api.responses.error.bases import AbstractErrorResponse
from quota.quota_exceed_error import QuotaExceedError


class PromptTooLongResponse(AbstractErrorResponse):
    """413 Payload Too Large - Prompt is too long."""

    description: ClassVar[str] = PROMPT_TOO_LONG_DESCRIPTION
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "context window exceeded",
                    "detail": {
                        "response": "Context window exceeded",
                        "cause": (
                            "The input exceeds the context window size "
                            "of model 'gpt-4o-mini'."
                        ),
                    },
                },
                {
                    "label": "prompt too long",
                    "detail": {
                        "response": "Prompt is too long",
                        "cause": "The prompt exceeds the maximum allowed length.",
                    },
                },
            ]
        }
    }

    def __init__(
        self,
        *,
        response: str = "Prompt is too long",
        model: Optional[str] = None,
    ) -> None:
        """Initialize a PromptTooLongResponse.

        Args:
            response: Short summary of the error. Defaults to "Prompt is too long".
            model: The model identifier for which the prompt is too long.
        """
        if model:
            cause = f"The input exceeds the context window size of model '{model}'."
        else:
            cause = "The prompt exceeds the maximum allowed length."

        super().__init__(
            response=response,
            cause=cause,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )


class FileTooLargeResponse(AbstractErrorResponse):
    """413 Content Too Large - File upload exceeds size limit."""

    description: ClassVar[str] = "File upload exceeds size limit"
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "file upload",
                    "detail": {
                        "response": "File too large",
                        "cause": (
                            "File size 150000000 bytes exceeds maximum "
                            "allowed size of 104857600 bytes (100 MB)"
                        ),
                    },
                },
                {
                    "label": "backend rejection",
                    "detail": {
                        "response": "Invalid file upload",
                        "cause": "File upload rejected: File size exceeds limit",
                    },
                },
            ]
        }
    }

    @classmethod
    def exceeds_local_limit(
        cls,
        *,
        file_size: int,
        max_size: int,
        response: str = "File too large",
    ) -> "FileTooLargeResponse":
        """Build a 413 when measured bytes exceed the configured upload maximum.

        Parameters:
            file_size: Measured size of the upload in bytes.
            max_size: Configured maximum allowed size in bytes.
            response: Short summary shown to the client.
        Returns:
            FileTooLargeResponse with a cause that includes both sizes and the size in MB (floored).
        """
        cause = (
            f"File size {file_size} bytes exceeds maximum allowed "
            f"size of {max_size} bytes ({max_size // (1024 * 1024)} MB)"
        )
        return cls(response=response, cause=cause)

    @classmethod
    def from_backend_rejection(
        cls,
        *,
        message: str,
        response: str = "Invalid file upload",
    ) -> "FileTooLargeResponse":
        """
        Build a 413 when Llama Stack rejects the upload after we sent it.

        Parameters:
            message: Error text from the backend.
            response: Short summary shown to the client.

        Returns:
            FileTooLargeResponse whose cause prefixes the message with a fixed label.
        """
        cause = f"File upload rejected: {message}"
        return cls(response=response, cause=cause)

    def __init__(self, *, response: str, cause: str) -> None:
        """Create a 413 Content Too Large error with explicit summary and cause.

        Parameters:
            response: Short summary of the error.
            cause: Detailed explanation for operators and clients.
        """
        super().__init__(
            response=response,
            cause=cause,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )


class UnprocessableEntityResponse(AbstractErrorResponse):
    """422 Unprocessable Entity - Request validation failed."""

    description: ClassVar[str] = UNPROCESSABLE_CONTENT_DESCRIPTION
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "invalid format",
                    "detail": {
                        "response": "Invalid request format",
                        "cause": "Invalid request format. The request body could not be parsed.",
                    },
                },
                {
                    "label": "missing attributes",
                    "detail": {
                        "response": "Missing required attributes",
                        "cause": "Missing required attributes: ['query', 'model', 'provider']",
                    },
                },
                {
                    "label": "invalid value",
                    "detail": {
                        "response": "Invalid attribute value",
                        "cause": "Invalid attachment type: must be one of ['text/plain', "
                        "'application/json', 'application/yaml', 'application/xml']",
                    },
                },
            ]
        }
    }

    def __init__(self, *, response: str, cause: str):
        """
        Create a 422 Unprocessable Entity error response.

        Parameters:
        ----------
            response (str): Human-readable error message describing what was unprocessable.
            cause (str): Specific cause or diagnostic information explaining the error.
        """
        super().__init__(
            response=response,
            cause=cause,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


class QuotaExceededResponse(AbstractErrorResponse):
    """429 Too Many Requests - Quota limit exceeded."""

    description: ClassVar[str] = QUOTA_EXCEEDED_DESCRIPTION
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "model",
                    "detail": {
                        "response": "The model quota has been exceeded",
                        "cause": "The token quota for model gpt-4-turbo has been exceeded.",
                    },
                },
                {
                    "label": "user none",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "User 123 has no available tokens.",
                    },
                },
                {
                    "label": "cluster none",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "Cluster has no available tokens.",
                    },
                },
                {
                    "label": "subject none",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "Unknown subject 999 has no available tokens.",
                    },
                },
                {
                    "label": "user insufficient",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "User 123 has 5 tokens, but 10 tokens are needed.",
                    },
                },
                {
                    "label": "cluster insufficient",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "Cluster has 500 tokens, but 900 tokens are needed.",
                    },
                },
                {
                    "label": "subject insufficient",
                    "detail": {
                        "response": "The quota has been exceeded",
                        "cause": "Unknown subject 999 has 3 tokens, but 6 tokens are needed.",
                    },
                },
            ]
        }
    }

    @classmethod
    def model(cls, model_name: str) -> "QuotaExceededResponse":
        """
        Create a QuotaExceededResponse for a specific model.

        Parameters:
        ----------
            model_name (str): The model identifier whose token quota was exceeded.

        Returns:
        -------
            QuotaExceededResponse: Response with a standard response message
            and a cause that includes the model name.
        """
        response = "The model quota has been exceeded"
        cause = f"The token quota for model {model_name} has been exceeded."
        return cls(response=response, cause=cause)

    @classmethod
    def from_exception(cls, exc: QuotaExceedError) -> "QuotaExceededResponse":
        """
        Construct a QuotaExceededResponse representing the provided QuotaExceedError.

        Parameters:
        ----------
            exc: The QuotaExceedError instance whose message will be used as
                 the cause.

        Returns:
        -------
            QuotaExceededResponse initialized with a standard quota-exceeded
            message and the exception's text as the cause.
        """
        response = "The quota has been exceeded"
        cause = str(exc)
        return cls(response=response, cause=cause)

    def __init__(self, *, response: str, cause: str) -> None:
        """
        Create a QuotaExceededResponse with a public message and an explanatory cause.

        Parameters:
        ----------
            response (str): Public-facing error message describing the quota condition.
            cause (str): Detailed cause or internal explanation for the quota
                         exceedance; stored in the error detail.

        Notes:
        -----
            Sets the response's HTTP status code to 429 (Too Many Requests).
        """
        super().__init__(
            response=response,
            cause=cause,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
