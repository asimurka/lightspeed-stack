"""Public ids for conversations, agent runs, and display turn items."""

from __future__ import annotations

import uuid
from typing import Final, Literal, Optional

_CONVERSATION_PREFIX: Final[str] = "conv_"
_RUN_PREFIX: Final[str] = "resp_"
_MESSAGE_ITEM_PREFIX: Final[str] = "msg_"
_TOOL_CALL_ITEM_PREFIX: Final[str] = "tc_"
_TOOL_RESULT_ITEM_PREFIX: Final[str] = "tr_"
_REASONING_ITEM_PREFIX: Final[str] = "rsn_"
_SOURCES_ITEM_PREFIX: Final[str] = "src_"
_FILE_SEARCH_SOURCES_ITEM_PREFIX: Final[str] = "fs_"

type TurnItemIdKind = Literal[
    "message",
    "tool_call",
    "tool_result",
    "reasoning",
    "sources",
    "file_search_sources",
]


def new_conversation_id() -> str:
    """Generate a new conversation id for the client."""
    return f"{_CONVERSATION_PREFIX}{uuid.uuid4()}"


def new_run_id() -> str:
    """Generate a new response id for the client."""
    return f"{_RUN_PREFIX}{uuid.uuid4()}"


def new_message_item_id() -> str:
    """Generate a new display-history message turn-item id."""
    return f"{_MESSAGE_ITEM_PREFIX}{uuid.uuid4()}"


def new_tool_call_item_id() -> str:
    """Generate a new display-history tool-call turn-item id."""
    return f"{_TOOL_CALL_ITEM_PREFIX}{uuid.uuid4()}"


def new_tool_result_item_id() -> str:
    """Generate a new display-history tool-result turn-item id."""
    return f"{_TOOL_RESULT_ITEM_PREFIX}{uuid.uuid4()}"


def new_reasoning_item_id() -> str:
    """Generate a new display-history reasoning turn-item id."""
    return f"{_REASONING_ITEM_PREFIX}{uuid.uuid4()}"


def new_sources_item_id() -> str:
    """Generate a new display-history sources turn-item id."""
    return f"{_SOURCES_ITEM_PREFIX}{uuid.uuid4()}"


def new_file_search_sources_item_id() -> str:
    """Generate a new display-history file-search sources turn-item id."""
    return f"{_FILE_SEARCH_SOURCES_ITEM_PREFIX}{uuid.uuid4()}"


def turn_item_id(kind: TurnItemIdKind, explicit: Optional[str] = None) -> str:
    """Return a provider id when set, otherwise a new prefixed UUID."""
    if explicit:
        return explicit
    match kind:
        case "message":
            return new_message_item_id()
        case "tool_call":
            return new_tool_call_item_id()
        case "tool_result":
            return new_tool_result_item_id()
        case "reasoning":
            return new_reasoning_item_id()
        case "sources":
            return new_sources_item_id()
        case "file_search_sources":
            return new_file_search_sources_item_id()


def strip_conversation_prefix(conversation_id: str) -> str:
    """Remove the conversation prefix when present."""
    return conversation_id.removeprefix(_CONVERSATION_PREFIX)


def with_conversation_prefix(conversation_id: str) -> str:
    """Add the conversation prefix when missing."""
    return f"{_CONVERSATION_PREFIX}{conversation_id.removeprefix(_CONVERSATION_PREFIX)}"
