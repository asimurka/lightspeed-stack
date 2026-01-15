"""LLM query and response steps."""

import json
import requests
from behave import then, step  # pyright: ignore[reportAttributeAccessIssue]
from behave.runner import Context
from tests.e2e.utils.utils import replace_placeholders


DEFAULT_LLM_TIMEOUT = 60


@step("I wait for the response to be completed")
def wait_for_complete_response(context: Context) -> None:
    """Wait for the response to be complete."""
    context.response_data = _parse_streaming_response(context.response.text)
    print(context.response_data)
    context.response.raise_for_status()
    assert context.response_data["finished"] is True


@step('I use "{endpoint}" to ask question')
def ask_question(context: Context, endpoint: str) -> None:
    """Call the service REST API endpoint with question."""
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path

    # Replace {MODEL} and {PROVIDER} placeholders with actual values
    json_str = replace_placeholders(context, context.text or "{}")

    data = json.loads(json_str)
    print(f"Request data: {data}")
    context.response = requests.post(url, json=data, timeout=DEFAULT_LLM_TIMEOUT)


@step('I use "{endpoint}" to ask question with authorization header')
def ask_question_authorized(context: Context, endpoint: str) -> None:
    """Call the service REST API endpoint with question."""
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path

    # Replace {MODEL} and {PROVIDER} placeholders with actual values
    json_str = replace_placeholders(context, context.text or "{}")

    data = json.loads(json_str)
    print(f"Request data: {data}")
    context.response = requests.post(
        url, json=data, headers=context.auth_headers, timeout=DEFAULT_LLM_TIMEOUT
    )


@step("I store conversation details")
def store_conversation_details(context: Context) -> None:
    """Store details about the conversation."""
    context.response_data = json.loads(context.response.text)


@step('I use "{endpoint}" to ask question with same conversation_id')
def ask_question_in_same_conversation(context: Context, endpoint: str) -> None:
    """Call the service REST API endpoint with question, but use the existing conversation id."""
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/{endpoint}".replace("//", "/")
    url = base + path

    # Replace {MODEL} and {PROVIDER} placeholders with actual values
    json_str = replace_placeholders(context, context.text or "{}")

    data = json.loads(json_str)
    headers = context.auth_headers if hasattr(context, "auth_headers") else {}
    data["conversation_id"] = context.response_data["conversation_id"]

    print(f"Request data: {data}")
    context.response = requests.post(
        url, json=data, headers=headers, timeout=DEFAULT_LLM_TIMEOUT
    )


@then("The response should have proper LLM response format")
def check_llm_response_format(context: Context) -> None:
    """Check the format of response from the service with LLM-generated answer."""
    assert context.response is not None
    response_json = context.response.json()
    assert "conversation_id" in response_json
    assert "response" in response_json


@then("The response should not be truncated")
def check_llm_response_not_truncated(context: Context) -> None:
    """Check that the response from LLM is not truncated."""
    assert context.response is not None
    response_json = context.response.json()
    assert response_json["truncated"] is False


@then("The response should contain following fragments")
def check_fragments_in_response(context: Context) -> None:
    """Check that all specified fragments are present in the LLM response.

    First checks that the HTTP response exists and contains a
    "response" field. For each fragment listed in the scenario's
    table under "Fragments in LLM response", asserts that it
    appears as a substring in the LLM's response. Raises an
    assertion error if any fragment is missing or if the fragments
    table is not provided.
    """
    assert context.response is not None
    response_json = context.response.json()
    response = response_json["response"]

    assert context.table is not None, "Fragments are not specified in table"

    for fragment in context.table:
        expected = fragment["Fragments in LLM response"]
        assert (
            expected in response
        ), f"Fragment '{expected}' not found in LLM response: '{response}'"


@then("The streamed response should contain following fragments")
def check_streamed_fragments_in_response(context: Context) -> None:
    """Check that all specified fragments are present in the LLM response.

    First checks that the HTTP response exists and contains a
    "response" field. For each fragment listed in the scenario's
    table under "Fragments in LLM response", asserts that it
    appears as a substring in the LLM's response. Raises an
    assertion error if any fragment is missing or if the fragments
    table is not provided.
    """
    assert context.response_data["response_complete"] is not None
    response = context.response_data["response"]

    assert context.table is not None, "Fragments are not specified in table"

    for fragment in context.table:
        expected = fragment["Fragments in LLM response"]
        assert (
            expected in response
        ), f"Fragment '{expected}' not found in LLM response: '{response}'"


@then("The streamed response is equal to the full response")
def compare_streamed_responses(context: Context) -> None:
    """Check that streamed response is equal to complete response.

    First checks that the HTTP response exists and contains a
    "response" field. Do this check also for the complete response
    Then assert that the response is not empty and that it is equal
    to complete response
    """
    assert context.response_data["response"] is not None
    assert context.response_data["response_complete"] is not None

    response = context.response_data["response"]
    complete_response = context.response_data["response_complete"]

    assert response != "", "response is empty"
    assert (
        response == complete_response
    ), f"{response} and {complete_response} do not match"


@step("I verify that shields are configured")
def verify_shields_configured(context: Context) -> None:
    """Verify that at least one shield is configured in the system."""
    base = f"http://{context.hostname}:{context.port}"
    path = f"{context.api_prefix}/shields".replace("//", "/")
    url = base + path
    headers = context.auth_headers if hasattr(context, "auth_headers") else {}

    response = requests.get(url, headers=headers, timeout=DEFAULT_LLM_TIMEOUT)
    response.raise_for_status()

    response_json = response.json()
    assert "shields" in response_json, "Response missing 'shields' field"
    shields = response_json["shields"]
    assert len(shields) > 0, "No shields are configured in the system"

    # Store shields info in context for potential later use
    context.shields = shields


@then("The response contains moderation message")
def check_moderation_message(context: Context) -> None:
    """Check that the response contains text indicating moderation was used.

    This checks for common moderation-related phrases like "policy restrictions",
    "cannot process", etc. that indicate shield moderation blocked the request.
    """
    assert context.response is not None, "Request needs to be performed first"
    response_json = context.response.json()

    assert "response" in response_json, "Response missing 'response' field"
    response_text = response_json["response"].lower()

    # Check for common moderation-related phrases
    moderation_phrases = [
        "policy restrictions",
        "cannot process",
        "i cannot",
        "restricted",
        "policy",
    ]

    found = any(phrase in response_text for phrase in moderation_phrases)
    assert found, (
        f"Response does not contain moderation-related text. "
        f"Response was: '{response_json['response']}'"
    )


@then("The streamed response contains moderation message")
def check_streamed_moderation_message(context: Context) -> None:
    """Check that the streamed response contains text indicating moderation was used.

    This checks for common moderation-related phrases in the streamed response
    that indicate shield moderation blocked the request.
    """
    assert hasattr(context, "response_data"), "Streaming response data not available"
    assert "response" in context.response_data, "Response data missing 'response' field"

    response_text = context.response_data["response"].lower()

    # Check for common moderation-related phrases
    moderation_phrases = [
        "policy restrictions",
        "cannot process",
        "i cannot",
        "restricted",
        "policy",
    ]

    found = any(phrase in response_text for phrase in moderation_phrases)
    assert found, (
        f"Streamed response does not contain moderation-related text. "
        f"Response was: '{context.response_data['response']}'"
    )


def _parse_streaming_response(response_text: str) -> dict:
    """Parse streaming SSE response and reconstruct the full message."""
    lines = response_text.strip().split("\n")
    conversation_id = None
    full_response = ""
    full_response_split = []
    finished = False
    first_token = True

    for line in lines:
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])  # Remove 'data: ' prefix
                event = data.get("event")

                if event == "start":
                    conversation_id = data["data"]["conversation_id"]
                elif event == "token":
                    # Skip the first token (shield status message)
                    if first_token:
                        first_token = False
                        continue
                    full_response_split.append(data["data"]["token"])
                elif event == "turn_complete":
                    full_response = data["data"]["token"]
                elif event == "end":
                    finished = True
            except json.JSONDecodeError:
                continue  # Skip malformed lines

    return {
        "conversation_id": conversation_id,
        "response": "".join(full_response_split),
        "response_complete": full_response,
        "finished": finished,
    }
