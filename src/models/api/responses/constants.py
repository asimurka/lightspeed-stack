"""Shared string constants for REST API response OpenAPI metadata."""

SUCCESSFUL_RESPONSE_DESCRIPTION = "Successful response"
BAD_REQUEST_DESCRIPTION = "Invalid request format"
UNAUTHORIZED_DESCRIPTION = "Unauthorized"
FORBIDDEN_DESCRIPTION = "Permission denied"
NOT_FOUND_DESCRIPTION = "Resource not found"
UNPROCESSABLE_CONTENT_DESCRIPTION = "Request validation failed"
INVALID_FEEDBACK_PATH_DESCRIPTION = "Invalid feedback storage path"
SERVICE_UNAVAILABLE_DESCRIPTION = "Service unavailable"
QUOTA_EXCEEDED_DESCRIPTION = "Quota limit exceeded"
PROMPT_TOO_LONG_DESCRIPTION = "Prompt is too long"
INTERNAL_SERVER_ERROR_DESCRIPTION = "Internal server error"
UNAUTHORIZED_OPENAPI_EXAMPLES: list[str] = [
    "missing header",
    "missing token",
    "expired token",
    "invalid signature",
    "invalid key",
    "missing claim",
    "invalid k8s token",
    "invalid jwk token",
]

UNAUTHORIZED_OPENAPI_EXAMPLES_WITH_MCP_OAUTH: list[str] = [
    *UNAUTHORIZED_OPENAPI_EXAMPLES,
    "mcp oauth",
]
