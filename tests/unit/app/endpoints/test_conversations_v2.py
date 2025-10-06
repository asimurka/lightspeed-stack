# pylint: disable=redefined-outer-name

"""Unit tests for the /conversations REST API endpoints."""

from app.endpoints.conversations_v2 import transform_chat_message

from models.cache_entry import CacheEntry


def test_transform_message() -> None:
    """Test the transform_chat_message transformation function."""
    entry = CacheEntry(
        query="query",
        response="response",
        provider="provider",
        model="model",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:00:05Z",
    )
    transformed = transform_chat_message(entry)
    assert transformed is not None

    assert "provider" in transformed
    assert transformed["provider"] == "provider"

    assert "model" in transformed
    assert transformed["model"] == "model"

    assert "started_at" in transformed
    assert transformed["started_at"] == "2024-01-01T00:00:00Z"

    assert "completed_at" in transformed
    assert transformed["completed_at"] == "2024-01-01T00:00:05Z"

    assert "messages" in transformed
    assert len(transformed["messages"]) == 2

    message1 = transformed["messages"][0]
    assert message1["type"] == "user"
    assert message1["content"] == "query"

    message2 = transformed["messages"][1]
    assert message2["type"] == "assistant"
    assert message2["content"] == "response"
