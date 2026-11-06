"""FastAPI exception handlers for domain errors."""

from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from conversations.display_history.errors import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    DisplayHistoryDatabaseError,
)
from log import get_logger
from models.api.responses.error import (
    ForbiddenResponse,
    InternalServerErrorResponse,
    NotFoundResponse,
)

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain-error handlers to the FastAPI application.

    Args:
        app: Application that should convert display-history errors into HTTP
            responses.

    """
    app.add_exception_handler(
        ConversationNotFoundError,
        cast(ExceptionHandler, conversation_not_found_handler),
    )
    app.add_exception_handler(
        ConversationAccessDeniedError,
        cast(ExceptionHandler, conversation_access_denied_handler),
    )
    app.add_exception_handler(
        DisplayHistoryDatabaseError,
        cast(ExceptionHandler, display_history_database_error_handler),
    )


def conversation_not_found_handler(
    _request: Request, exc: ConversationNotFoundError
) -> JSONResponse:
    """Map a missing conversation onto HTTP 404."""
    logger.error("No conversation found for conversation ID %s", exc.conversation_id)
    error = NotFoundResponse(resource="conversation", resource_id=exc.conversation_id)
    return JSONResponse(
        status_code=error.status_code, content=error.detail.model_dump()
    )


def conversation_access_denied_handler(
    request: Request, exc: ConversationAccessDeniedError
) -> JSONResponse:
    """Map a forbidden conversation onto HTTP 403."""
    match request.method:
        case "GET":
            action = "read"
        case "DELETE":
            action = "delete"
        case "PUT" | "PATCH":
            action = "update"
        case _:
            action = "access"
    logger.warning(
        "User %s attempted to %s conversation %s they don't have access to",
        exc.user_id,
        action,
        exc.conversation_id,
    )
    error = ForbiddenResponse.conversation(
        action=action,
        resource_id=exc.conversation_id,
        user_id=exc.user_id,
    )
    return JSONResponse(
        status_code=error.status_code, content=error.detail.model_dump()
    )


def display_history_database_error_handler(
    _request: Request, exc: DisplayHistoryDatabaseError
) -> JSONResponse:
    """Map a display-history database failure onto HTTP 500."""
    logger.error("Display history %s failed", exc.operation)
    error = InternalServerErrorResponse.database_error()
    return JSONResponse(
        status_code=error.status_code, content=error.detail.model_dump()
    )
