"""Map a PAI agent run onto OpenResponses terminal status.

Mirrors conversations display-history ``project_agent_turn_summary`` finish
reasons, with OpenResponses statuses: cancelled and max-length become
``incomplete``, provider errors become ``failed``, and content filters stay
``completed`` with refusal text.
"""

from typing import Any, Literal, Optional

from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import DeferredToolRequests

from responses.models.config import ResponseError
from responses.projector.refusal import DEFAULT_REFUSAL_TEXT

ResponseStatus = Literal["in_progress", "completed", "failed", "incomplete"]


def terminal_from_run(
    result: AgentRunResult[Any],
) -> tuple[ResponseStatus, Optional[ResponseError], Optional[str]]:
    """Return status, optional error, and optional refusal text for a run.

    Args:
        result: Completed PAI agent run.

    Returns:
        Terminal status, error object when the run failed, and refusal text
        when a content filter blocked the turn.

    """
    if isinstance(result.output, DeferredToolRequests):
        return "completed", None, None
    try:
        response = result.response
    except ValueError:
        return "completed", None, None
    details = response.provider_details or {}
    reason = response.finish_reason
    if details.get("finish_reason") == "cancelled" or reason == "length":
        return "incomplete", None, None
    if reason == "content_filter":
        refusal = details.get("refusal_response")
        text = refusal if isinstance(refusal, str) and refusal else DEFAULT_REFUSAL_TEXT
        return "completed", None, text
    if reason == "error":
        message = details.get("error")
        return (
            "failed",
            ResponseError(
                code="server_error",
                message=(
                    message
                    if isinstance(message, str) and message
                    else "The model reported an error."
                ),
            ),
            None,
        )
    return "completed", None, None
