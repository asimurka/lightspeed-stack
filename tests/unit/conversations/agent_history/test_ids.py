"""Tests for conversation and turn item id helpers."""

import uuid

from conversations.agent_history.ids import (
    new_file_search_sources_item_id,
    new_message_item_id,
    new_run_id,
    turn_item_id,
)


def test_message_item_id_matches_run_id_shape() -> None:
    """Turn item ids use the same ``{prefix}{uuid4}`` pattern as run ids."""
    item_id = new_message_item_id()
    assert item_id.startswith("msg_")
    uuid.UUID(item_id.removeprefix("msg_"))

    run_id = new_run_id()
    assert run_id.startswith("resp_")
    uuid.UUID(run_id.removeprefix("resp_"))


def test_turn_item_id_respects_explicit() -> None:
    """An explicit provider id is returned unchanged."""
    assert turn_item_id("tool_call", explicit="tc_provider") == "tc_provider"


def test_file_search_sources_prefix() -> None:
    """File-search sources items use the fs_ prefix."""
    item_id = new_file_search_sources_item_id()
    assert item_id.startswith("fs_")
    uuid.UUID(item_id.removeprefix("fs_"))
