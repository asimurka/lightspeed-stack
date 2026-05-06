"""Health-related shared models for readiness and diagnostics."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health status enum for provider health checks."""

    OK = "ok"
    ERROR = "Error"
    NOT_IMPLEMENTED = "not_implemented"
    HEALTHY = "healthy"
    UNKNOWN = "unknown"


class ProviderHealthStatus(BaseModel):
    """Model representing the health status of a provider.

    Attributes:
        provider_id: The ID of the provider.
        status: The health status ('ok', 'unhealthy', 'not_implemented').
        message: Optional message about the health status.
    """

    provider_id: str = Field(
        description="The ID of the provider",
    )
    status: str = Field(
        description="The health status",
        examples=["ok", "unhealthy", "not_implemented"],
    )
    message: Optional[str] = Field(
        None,
        description="Optional message about the health status",
        examples=["All systems operational", "Llama Stack is unavailable"],
    )
