"""Project a PAI run into an agentic-turn persistence summary."""

from __future__ import annotations

from typing import Any, Optional

from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ModelResponse
from pydantic_ai.run import AgentRunResult

from conversations.display_history.agentic.models.agent_turn_summary import (
    AgentTurnSummary,
)
from conversations.display_history.agentic.models.types import AgentTurnStatus
from conversations.display_history.agentic.projection.items import (
    turn_items_from_messages,
)
from models.common.agents import AgentRunDeps

type AgentRunOutcome = AgentRunResult[Any] | RunCancelled
"""Completed agent run or a cancelled run that still has message history."""


def project_agent_turn_summary(
    run: AgentRunOutcome,
    deps: AgentRunDeps,
) -> Optional[AgentTurnSummary]:
    """Convert a PAI run into persistence fields for ``user_agentic_turn``.

    Status, usage, and items come from the run. Compaction status and inline
    citations come from ``deps``. ``agent`` is always unset until the run
    result (or another source) can supply a PAI agent name.

    ``RunCancelled.run_id`` is ``None`` when the run was cancelled before it
    started. Those runs have no step-store identity, so they are not projected.

    Args:
        run: Completed ``AgentRunResult`` or ``RunCancelled`` snapshot.
        deps: Per-run collector mutated by capabilities.

    Returns:
        Persistence summary, or ``None`` when there is no ``run_id``.

    """
    if not run.run_id:
        return None
    input_items, output_items, run_documents = turn_items_from_messages(
        run.new_messages()
    )
    return AgentTurnSummary(
        status=_status_from_run(run),
        agent=None,
        context_status=deps.context_status,
        input_tokens=run.usage.input_tokens,
        output_tokens=run.usage.output_tokens,
        referenced_documents=[*deps.referenced_documents, *run_documents],
        input=input_items,
        output=output_items,
    )


def _status_from_run(run: AgentRunOutcome) -> AgentTurnStatus:
    """Map PAI completion or cancellation onto a stored turn status."""
    if isinstance(run, RunCancelled):
        return "interrupted"
    try:
        response = run.response
    except ValueError:
        return "failed"
    return _status_from_response(response)


def _status_from_response(response: ModelResponse) -> AgentTurnStatus:
    """Map a PAI model response finish reason onto a stored turn status."""
    details = response.provider_details or {}
    if details.get("finish_reason") == "cancelled":
        return "interrupted"
    match response.finish_reason:
        case "stop" | "content_filter":
            return "completed"
        case "length" | "error":
            return "failed"
        case "tool_call":
            return "awaiting_input"
        case _:
            return "completed"
