"""Store an agentic display turn next to the conversation/turn envelope."""

from __future__ import annotations

from typing import Optional

from conversations.display_history.agentic.projection import (
    AgentRunOutcome,
    project_agent_turn_summary,
)
from conversations.display_history.persistence.models import UserAgenticTurn
from conversations.display_history.persistence.repository.agentic_turn import (
    insert_agentic_turn,
)
from log import get_logger
from models.common.agents import AgentRunDeps
from utils.suid import normalize_conversation_id

logger = get_logger(__name__)


def store_agentic_turn(
    conversation_id: str,
    turn_number: int,
    run: AgentRunOutcome,
    deps: AgentRunDeps,
) -> Optional[UserAgenticTurn]:
    """Project a PAI run and persist agentic display history for a turn envelope.

    The conversation row and ``user_turn`` envelope must already exist. This
    writes only the ``user_agentic_turn`` projection (status, items, usage).

    Runs cancelled before they started have no ``run_id`` and are skipped: they
    cannot be referenced in the step store.

    Args:
        conversation_id: Conversation that owns the turn (prefix optional).
        turn_number: Envelope turn number to attach agentic data to.
        run: Completed or cancelled PAI run.
        deps: Per-run collector mutated by capabilities.

    Returns:
        The saved agentic turn row, or ``None`` when the run has no ``run_id``.

    """
    summary = project_agent_turn_summary(run, deps)
    if summary is None:
        logger.debug("Skipping agentic persist: run was cancelled before it started")
        return None
    normalized = normalize_conversation_id(conversation_id)
    logger.debug(
        "Storing agentic turn conversation_id=%s turn_number=%s status=%s",
        normalized,
        turn_number,
        summary.status,
    )
    return insert_agentic_turn(normalized, turn_number, summary)
