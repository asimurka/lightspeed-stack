"""HTTP 5xx error response models."""

from models.api.responses.error.server.availability import ServiceUnavailableResponse
from models.api.responses.error.server.internal import InternalServerErrorResponse

__all__ = [
    "InternalServerErrorResponse",
    "ServiceUnavailableResponse",
]
