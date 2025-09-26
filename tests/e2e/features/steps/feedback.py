"""Implementation of common test steps."""

from behave import given, when  # pyright: ignore[reportAttributeAccessIssue]
from behave.runner import Context
import requests
from tests.e2e.utils.utils import validate_json_partially

# default timeout for HTTP operations
DEFAULT_TIMEOUT = 10


@when(
    "I access endpoint {endpoint:w} using HTTP POST with conversation ID {conversationID:w}"
)  # type: ignore
def access_rest_api_endpoint_post(
    context: Context, endpoint: str, conversation_id: str
) -> None:
    """Send POST HTTP request with JSON payload to tested service.

    The JSON payload is retrieved from `context.text` attribute,
    which must not be None. The response is stored in
    `context.response` attribute.
    """
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path

    assert conversation_id is not None, "Payload needs to be specified"
    # TODO: finish the conversation ID handling

    # perform REST API call
    context.response = requests.post(url, timeout=DEFAULT_TIMEOUT)


@given("The feedback is enabled")  # type: ignore 
@when("I enable the feedback")  # type: ignore 
def enable_feedback(context: Context) -> None:
    """Enable feedback."""
    assert context is not None
    _set_feedback(context, True)
    assert context.response is True, "Incorrect response"

@given("The feedback is disabled")  # type: ignore 
@when("I disable the feedback")  # type: ignore 
def disable_feedback(context: Context) -> None:
    """Disable feedback."""
    assert context is not None
    _set_feedback(context, False)
    assert context.response is False, "Incorrect response"


def _set_feedback(context, enabled: bool):
    """
    Internal helper to enable or disable feedback.
    Stores the HTTP response in context.last_response.
    """
    endpoint = "feedback/status"
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "status": enabled
    }
    response = requests.post(url, headers=headers, json=payload)
    context.response = response

@when("I toggle the feedback with")  # type: ignore
def toggle_feedback(context):
    assert context is not None
    endpoint = "feedback/status"
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=context.text.json())
    context.response = response
