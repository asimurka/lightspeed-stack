"""401/403 authentication and authorization error responses."""

from typing import ClassVar

from fastapi import status

from models.api.responses.constants import (
    FORBIDDEN_DESCRIPTION,
    UNAUTHORIZED_DESCRIPTION,
)
from models.api.responses.error.bases import AbstractErrorResponse
from models.config import Action


class UnauthorizedResponse(AbstractErrorResponse):
    """401 Unauthorized - Missing or invalid credentials."""

    description: ClassVar[str] = UNAUTHORIZED_DESCRIPTION
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "missing header",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "No Authorization header found",
                    },
                },
                {
                    "label": "missing token",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "No token found in Authorization header",
                    },
                },
                {
                    "label": "expired token",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Token has expired",
                    },
                },
                {
                    "label": "invalid signature",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Invalid token signature",
                    },
                },
                {
                    "label": "invalid key",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Token signed by unknown key",
                    },
                },
                {
                    "label": "missing claim",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Token missing claim: user_id",
                    },
                },
                {
                    "label": "invalid k8s token",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Invalid or expired Kubernetes token",
                    },
                },
                {
                    "label": "invalid jwk token",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": "Authentication key server returned invalid data",
                    },
                },
                {
                    "label": "mcp oauth",
                    "detail": {
                        "response": "Missing or invalid credentials provided by client",
                        "cause": (
                            "MCP server at https://mcp.example.com/v1 requires OAuth"
                        ),
                    },
                },
            ]
        }
    }

    def __init__(self, *, cause: str):
        """
        Create an UnauthorizedResponse describing missing or invalid client credentials.

        Initializes the error with a standardized response message and the
        provided cause, and sets the HTTP status to 401 Unauthorized.

        Parameters:
        ----------
                cause (str): Human-readable explanation of why the request is
                             unauthorized (e.g. "missing token", "token expired").
        """
        response_msg = "Missing or invalid credentials provided by client"
        super().__init__(
            response=response_msg, cause=cause, status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenResponse(AbstractErrorResponse):
    """403 Forbidden. Access denied."""

    description: ClassVar[str] = FORBIDDEN_DESCRIPTION
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "label": "conversation read",
                    "detail": {
                        "response": "User does not have permission to perform this action",
                        "cause": (
                            "User 6789 does not have permission to read conversation "
                            "with ID 123e4567-e89b-12d3-a456-426614174000"
                        ),
                    },
                },
                {
                    "label": "conversation delete",
                    "detail": {
                        "response": "User does not have permission to perform this action",
                        "cause": (
                            "User 6789 does not have permission to delete conversation "
                            "with ID 123e4567-e89b-12d3-a456-426614174000"
                        ),
                    },
                },
                {
                    "label": "endpoint",
                    "detail": {
                        "response": "User does not have permission to access this endpoint",
                        "cause": "User 6789 is not authorized to access this endpoint.",
                    },
                },
                {
                    "label": "prompt read",
                    "detail": {
                        "response": "User does not have permission to perform this action",
                        "cause": (
                            "User 6789 does not have permission to list or read stored prompts "
                            "(missing permission: read_prompts)."
                        ),
                    },
                },
                {
                    "label": "prompt manage",
                    "detail": {
                        "response": "User does not have permission to perform this action",
                        "cause": (
                            "User 6789 does not have permission to create, update, or delete "
                            "stored prompts (missing permission: manage_prompts)."
                        ),
                    },
                },
                {
                    "label": "feedback",
                    "detail": {
                        "response": "Storing feedback is disabled",
                        "cause": "Storing feedback is disabled.",
                    },
                },
                {
                    "label": "model override",
                    "detail": {
                        "response": (
                            "This instance does not permit overriding model/provider in the "
                            "query request (missing permission: MODEL_OVERRIDE). Please remove "
                            "the model and provider fields from your request."
                        ),
                        "cause": (
                            "User lacks model_override permission required "
                            "to override model/provider."
                        ),
                    },
                },
            ]
        }
    }

    @classmethod
    def conversation(
        cls, action: str, resource_id: str, user_id: str
    ) -> "ForbiddenResponse":
        """
        Create a ForbiddenResponse for a denied conversation action.

        Parameters:
        ----------
            action (str): The attempted action (e.g., "read", "delete", "update").
            resource_id (str): The conversation identifier targeted by the action.
            user_id (str): The identifier of the user who attempted the action.

        Returns:
        -------
            ForbiddenResponse: Error response indicating the user is not
            permitted to perform the specified action on the conversation, with
            `response` and `cause` fields populated.
        """
        response = "User does not have permission to perform this action"
        cause = (
            f"User {user_id} does not have permission to "
            f"{action} conversation with ID {resource_id}"
        )
        return cls(response=response, cause=cause)

    @classmethod
    def endpoint(cls, user_id: str) -> "ForbiddenResponse":
        """
        Create a ForbiddenResponse indicating the specified user is denied access to the endpoint.

        Parameters:
        ----------
            user_id (str): Identifier of the user denied access.

        Returns:
        -------
            ForbiddenResponse: Error response with a message and a cause
            referencing the given `user_id`.
        """
        response = "User does not have permission to access this endpoint"
        cause = f"User {user_id} is not authorized to access this endpoint."
        return cls(response=response, cause=cause)

    @classmethod
    def feedback_disabled(cls) -> "ForbiddenResponse":
        """
        Create a ForbiddenResponse indicating that storing feedback is disabled.

        Returns:
            ForbiddenResponse: Error response with `response` set to "Storing
            feedback is disabled" and `cause` set to "Storing feedback is
            disabled."
        """
        return cls(
            response="Storing feedback is disabled",
            cause="Storing feedback is disabled.",
        )

    @classmethod
    def model_override(cls) -> "ForbiddenResponse":
        """
        Create a ForbiddenResponse indicating that overriding the model or provider is disallowed.

        Returns:
            ForbiddenResponse: An error response with a user-facing message
            instructing removal of model/provider fields and a cause stating
            the missing `MODEL_OVERRIDE` permission.
        """
        return cls(
            response=(
                "This instance does not permit overriding model/provider in the "
                "query request (missing permission: MODEL_OVERRIDE). Please remove "
                "the model and provider fields from your request."
            ),
            cause=(
                f"User lacks {Action.MODEL_OVERRIDE.value} permission required "
                "to override model/provider."
            ),
        )

    def __init__(self, *, response: str, cause: str):
        """
        Construct a ForbiddenResponse with a public response message and an internal cause.

        Parameters:
        ----------
                response (str): Human-facing error message describing the forbidden action.
                cause (str): Detailed cause or reason for the denial intended
                for logs or diagnostics.
        """
        super().__init__(
            response=response, cause=cause, status_code=status.HTTP_403_FORBIDDEN
        )
