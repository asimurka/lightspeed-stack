"""Implementation of common test steps."""

import os

from behave import given  # pyright: ignore[reportAttributeAccessIssue]
from behave.runner import Context


@given("The service is started locally")
def service_is_started_locally(context: Context) -> None:
    """Check the service status."""
    assert context is not None
    context.hostname = os.getenv("E2E_LSC_HOSTNAME", "localhost")
    context.port = os.getenv("E2E_LSC_PORT", "8080")
    context.hostname_llama = os.getenv("E2E_LLAMA_HOSTNAME", "localhost")
    context.port_llama = os.getenv("E2E_LLAMA_PORT", "8321")


@given("The system is in default state")
def system_in_default_state(context: Context) -> None:
    """Check the default system state."""
    assert context is not None
