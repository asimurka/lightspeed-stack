"""Read and mutate display-history conversations for the v3 Conversations API."""

from __future__ import annotations

from conversations.display_history.access import (
    check_conversation_access,
    get_user_conversation,
)
from conversations.display_history.agentic.models.agent_turn import AgentTurn
from conversations.display_history.agentic.models.conversation import (
    Conversation,
    ConversationMetadata,
)
from conversations.display_history.errors import ConversationAccessDeniedError
from conversations.display_history.persistence.models import (
    UserAgenticTurn,
    UserConversation,
    UserTurn,
)
from conversations.display_history.persistence.repository.agentic_turn import (
    list_agentic_turns_for_conversation,
)
from conversations.display_history.persistence.repository.conversation import (
    delete_conversation as delete_conversation_row,
)
from conversations.display_history.persistence.repository.conversation import (
    list_conversations as list_conversation_rows,
)
from conversations.display_history.persistence.repository.conversation import (
    list_conversations_for_user,
    update_conversation_topic_summary,
)
from conversations.display_history.persistence.repository.turn import (
    list_turns_for_conversation,
)
from log import get_logger
from utils.suid import normalize_conversation_id

logger = get_logger(__name__)


def list_conversations(
    user_id: str,
    others_allowed: bool,
) -> list[ConversationMetadata]:
    """List conversation envelopes the caller may see.

    Args:
        user_id: User requesting the list.
        others_allowed: Whether other users' conversations are included.

    Returns:
        Metadata rows without ``chat_history``.

    """
    rows = (
        list_conversation_rows()
        if others_allowed
        else list_conversations_for_user(user_id)
    )
    logger.info("Listed %s conversations for user %s", len(rows), user_id)
    return [_conversation_metadata(row) for row in rows]


def get_conversation(
    conversation_id: str,
    user_id: str,
    others_allowed: bool,
) -> Conversation:
    """Load one conversation envelope with ordered agent turns.

    Args:
        conversation_id: Conversation from the client (prefix optional).
        user_id: User requesting access.
        others_allowed: Whether other users' conversations are readable.

    Returns:
        Full conversation including ``chat_history``.

    Raises:
        ConversationAccessDeniedError: User may not read this conversation.
        ConversationNotFoundError: Conversation does not exist.
        DisplayHistoryDatabaseError: Database operation failed.

    """
    normalized = normalize_conversation_id(conversation_id)
    row = get_user_conversation(normalized, user_id, others_allowed)
    turns = list_turns_for_conversation(normalized)
    agentic_turns = list_agentic_turns_for_conversation(normalized)
    history = _chat_history(turns, agentic_turns)
    logger.info(
        "Loaded conversation %s for user %s with %s turns",
        normalized,
        user_id,
        len(history),
    )
    return Conversation(
        **_conversation_metadata(row).model_dump(),
        chat_history=history,
    )


def delete_conversation(
    conversation_id: str,
    user_id: str,
    others_allowed: bool,
) -> bool:
    """Delete a conversation when the caller is allowed.

    Missing conversations are not treated as forbidden; the caller receives
    ``False`` so the HTTP layer can match the v2 deleted flag.

    Args:
        conversation_id: Conversation from the client (prefix optional).
        user_id: User requesting deletion.
        others_allowed: Whether other users' conversations are writable.

    Returns:
        True if a row was removed.

    Raises:
        ConversationAccessDeniedError: User may not delete this conversation.
        DisplayHistoryDatabaseError: Database operation failed.

    """
    normalized = normalize_conversation_id(conversation_id)
    if not check_conversation_access(normalized, user_id, others_allowed):
        raise ConversationAccessDeniedError(normalized, user_id)
    deleted = delete_conversation_row(normalized)
    logger.info(
        "Deleted conversation %s for user %s: %s",
        normalized,
        user_id,
        deleted,
    )
    return deleted


def update_conversation_topic(
    conversation_id: str,
    user_id: str,
    others_allowed: bool,
    topic_summary: str,
) -> None:
    """Replace the topic summary when the caller is allowed.

    Args:
        conversation_id: Conversation from the client (prefix optional).
        user_id: User requesting the update.
        others_allowed: Whether other users' conversations are writable.
        topic_summary: Replacement topic summary.

    Raises:
        ConversationAccessDeniedError: User may not update this conversation.
        ConversationNotFoundError: Conversation does not exist.
        DisplayHistoryDatabaseError: Database operation failed.

    """
    normalized = normalize_conversation_id(conversation_id)
    get_user_conversation(normalized, user_id, others_allowed)
    update_conversation_topic_summary(normalized, topic_summary)
    logger.info(
        "Updated topic summary for conversation %s for user %s",
        normalized,
        user_id,
    )


def _conversation_metadata(row: UserConversation) -> ConversationMetadata:
    """Map a stored conversation row onto the public envelope."""
    return ConversationMetadata(
        conversation_id=row.id,
        created_at=row.created_at,
        last_turn_at=row.last_message_at,
        turn_count=row.message_count,
        last_used_model=row.last_used_model,
        last_used_provider=row.last_used_provider,
        topic_summary=row.topic_summary or None,
    )


def _chat_history(
    turns: list[UserTurn],
    agentic_turns: list[UserAgenticTurn],
) -> list[AgentTurn]:
    """Join turn envelopes with agentic display rows in turn-number order."""
    agentic_by_number = {row.turn_number: row for row in agentic_turns}
    history: list[AgentTurn] = []
    for turn in turns:
        agentic = agentic_by_number.get(turn.turn_number)
        if agentic is None or not turn.response_id:
            continue
        history.append(_agent_turn(turn, agentic))
    return history


def _agent_turn(turn: UserTurn, agentic: UserAgenticTurn) -> AgentTurn:
    """Assemble the public agent turn from envelope plus persisted summary."""
    return AgentTurn.model_validate(
        {
            "id": turn.response_id,
            "status": agentic.status,
            "agent": agentic.agent,
            "provider": turn.provider,
            "model": turn.model,
            "started_at": turn.started_at,
            "completed_at": turn.completed_at,
            "context_status": agentic.context_status,
            "usage": {
                "input_tokens": agentic.input_tokens,
                "output_tokens": agentic.output_tokens,
            },
            "referenced_documents": agentic.referenced_documents,
            "input": agentic.input_items,
            "output": agentic.output_items,
        }
    )
