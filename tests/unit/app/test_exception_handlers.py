"""Unit tests for display-history FastAPI exception handlers."""

import pytest
from fastapi import FastAPI, Request
from pytest_mock import MockerFixture

from app.exception_handlers import (
    conversation_access_denied_handler,
    conversation_not_found_handler,
    display_history_database_error_handler,
    register_exception_handlers,
)
from conversations.display_history.errors import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    DisplayHistoryDatabaseError,
)

CONVERSATION_ID = "123e4567-e89b-12d3-a456-426614174000"
USER_ID = "mock_user_id"


def _request(mocker: MockerFixture, method: str = "GET") -> Request:
    request = mocker.Mock(spec=Request)
    request.method = method
    return request


def test_register_exception_handlers() -> None:
    """Display-history errors are registered on the FastAPI app."""
    app = FastAPI()
    register_exception_handlers(app)
    assert ConversationNotFoundError in app.exception_handlers
    assert ConversationAccessDeniedError in app.exception_handlers
    assert DisplayHistoryDatabaseError in app.exception_handlers


def test_conversation_not_found_handler(mocker: MockerFixture) -> None:
    """Missing conversations become HTTP 404."""
    response = conversation_not_found_handler(
        _request(mocker),
        ConversationNotFoundError(CONVERSATION_ID),
    )
    assert response.status_code == 404
    assert response.body
    assert CONVERSATION_ID.encode() in response.body


def test_conversation_access_denied_handler_uses_http_method(
    mocker: MockerFixture,
) -> None:
    """Forbidden responses include the action inferred from the HTTP method."""
    response = conversation_access_denied_handler(
        _request(mocker, method="DELETE"),
        ConversationAccessDeniedError(CONVERSATION_ID, USER_ID),
    )
    assert response.status_code == 403
    assert b"delete conversation" in response.body
    assert USER_ID.encode() in response.body


@pytest.mark.parametrize(
    ("method", "action"),
    [
        ("GET", "read"),
        ("PUT", "update"),
        ("PATCH", "update"),
        ("POST", "access"),
    ],
)
def test_conversation_access_denied_action_from_method(
    mocker: MockerFixture, method: str, action: str
) -> None:
    """HTTP methods map onto conversation actions in the 403 cause."""
    response = conversation_access_denied_handler(
        _request(mocker, method=method),
        ConversationAccessDeniedError(CONVERSATION_ID, USER_ID),
    )
    assert action.encode() in response.body


def test_display_history_database_error_handler(mocker: MockerFixture) -> None:
    """Database failures become HTTP 500."""
    response = display_history_database_error_handler(
        _request(mocker),
        DisplayHistoryDatabaseError("list conversations"),
    )
    assert response.status_code == 500
    assert b"Database query failed" in response.body
