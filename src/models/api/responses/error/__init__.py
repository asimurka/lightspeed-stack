"""Structured client (4xx) and server (5xx) error responses for the REST API."""

from models.api.responses.error.bases import AbstractErrorResponse, DetailModel
from models.api.responses.error.client.auth import (
    ForbiddenResponse,
    UnauthorizedResponse,
)
from models.api.responses.error.client.bad_request import BadRequestResponse
from models.api.responses.error.client.conflict import ConflictResponse
from models.api.responses.error.client.not_found import NotFoundResponse
from models.api.responses.error.client.payload import (
    FileTooLargeResponse,
    PromptTooLongResponse,
    QuotaExceededResponse,
    UnprocessableEntityResponse,
)
from models.api.responses.error.server.availability import ServiceUnavailableResponse
from models.api.responses.error.server.internal import InternalServerErrorResponse

__all__ = [
    "AbstractErrorResponse",
    "BadRequestResponse",
    "ConflictResponse",
    "DetailModel",
    "FileTooLargeResponse",
    "ForbiddenResponse",
    "InternalServerErrorResponse",
    "NotFoundResponse",
    "PromptTooLongResponse",
    "QuotaExceededResponse",
    "ServiceUnavailableResponse",
    "UnauthorizedResponse",
    "UnprocessableEntityResponse",
]
