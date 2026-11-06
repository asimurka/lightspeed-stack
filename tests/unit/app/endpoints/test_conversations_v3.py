"""Unit tests for the /v3/conversations REST API endpoints."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, status
from pytest_mock import MockerFixture

from app.endpoints.conversations_v3 import (
    check_valid_conversation_id,
    delete_conversation_endpoint_handler,
    get_conversation_endpoint_handler,
    get_conversations_list_endpoint_handler,
    update_conversation_endpoint_handler,
)
from configuration import AppConfig
from conversations.display_history.agentic.models.conversation import (
    Conversation,
    ConversationMetadata,
)
from conversations.display_history.errors import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    DisplayHistoryDatabaseError,
)
from models.api.requests import ConversationUpdateRequest
from tests.unit.utils.auth_helpers import mock_authorization_resolvers

MOCK_AUTH = ("mock_user_id", "mock_username", False, "mock_token")
VALID_CONVERSATION_ID = "123e4567-e89b-12d3-a456-426614174000"
INVALID_CONVERSATION_ID = "invalid-id"


def _metadata() -> ConversationMetadata:
    return ConversationMetadata(
        conversation_id=VALID_CONVERSATION_ID,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        topic_summary="summary",
    )


def _conversation() -> Conversation:
    return Conversation(
        conversation_id=VALID_CONVERSATION_ID,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        topic_summary="summary",
        chat_history=[],
    )


class TestCheckValidConversationId:
    """Test cases for the check_valid_conversation_id function."""

    def test_valid_conversation_id(self) -> None:
        """A UUID conversation ID is accepted."""
        check_valid_conversation_id(VALID_CONVERSATION_ID)

    def test_invalid_conversation_id(self) -> None:
        """An invalid conversation ID raises HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            check_valid_conversation_id(INVALID_CONVERSATION_ID)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        response = detail["response"]  # pyright: ignore[reportArgumentType]
        assert "Invalid conversation ID format" in response


class TestGetConversationsListEndpoint:
    """Test cases for the GET /v3/conversations endpoint."""

    @pytest.mark.asyncio
    async def test_configuration_not_loaded(self, mocker: MockerFixture) -> None:
        """Test the endpoint when configuration is not loaded."""
        mock_authorization_resolvers(mocker)
        mock_config = AppConfig()
        mock_config._configuration = None  # pylint: disable=protected-access
        mocker.patch("app.endpoints.conversations_v3.configuration", mock_config)

        with pytest.raises(HTTPException) as exc_info:
            await get_conversations_list_endpoint_handler(
                request=mocker.Mock(),
                auth=MOCK_AUTH,
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_successful_retrieval(self, mocker: MockerFixture) -> None:
        """Test successful retrieval of the conversation list."""
        mock_authorization_resolvers(mocker)
        mocker.patch(
            "app.endpoints.conversations_v3.check_configuration_loaded",
        )
        mocker.patch(
            "app.endpoints.conversations_v3.list_conversations",
            return_value=[_metadata()],
        )

        response = await get_conversations_list_endpoint_handler(
            request=mocker.Mock(),
            auth=MOCK_AUTH,
        )

        assert len(response.conversations) == 1
        assert response.conversations[0].conversation_id == VALID_CONVERSATION_ID

    @pytest.mark.asyncio
    async def test_database_error(self, mocker: MockerFixture) -> None:
        """Display-history database failures propagate for the app handler."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.list_conversations",
            side_effect=DisplayHistoryDatabaseError("list conversations"),
        )

        with pytest.raises(DisplayHistoryDatabaseError):
            await get_conversations_list_endpoint_handler(
                request=mocker.Mock(),
                auth=MOCK_AUTH,
            )


class TestGetConversationEndpoint:
    """Test cases for the GET /v3/conversations/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_successful_retrieval(self, mocker: MockerFixture) -> None:
        """Test successful retrieval of a conversation."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.get_conversation",
            return_value=_conversation(),
        )

        response = await get_conversation_endpoint_handler(
            request=mocker.Mock(),
            conversation_id=VALID_CONVERSATION_ID,
            auth=MOCK_AUTH,
        )

        assert response.conversation_id == VALID_CONVERSATION_ID
        assert response.chat_history == []

    @pytest.mark.asyncio
    async def test_not_found(self, mocker: MockerFixture) -> None:
        """Missing conversations become HTTP 404."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.get_conversation",
            side_effect=ConversationNotFoundError(VALID_CONVERSATION_ID),
        )

        with pytest.raises(ConversationNotFoundError):
            await get_conversation_endpoint_handler(
                request=mocker.Mock(),
                conversation_id=VALID_CONVERSATION_ID,
                auth=MOCK_AUTH,
            )

    @pytest.mark.asyncio
    async def test_forbidden(self, mocker: MockerFixture) -> None:
        """Access denied becomes HTTP 403."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.get_conversation",
            side_effect=ConversationAccessDeniedError(
                VALID_CONVERSATION_ID, MOCK_AUTH[0]
            ),
        )

        with pytest.raises(ConversationAccessDeniedError):
            await get_conversation_endpoint_handler(
                request=mocker.Mock(),
                conversation_id=VALID_CONVERSATION_ID,
                auth=MOCK_AUTH,
            )

    @pytest.mark.asyncio
    async def test_invalid_conversation_id(self, mocker: MockerFixture) -> None:
        """Invalid IDs become HTTP 400 before the facade is called."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        get_mock = mocker.patch("app.endpoints.conversations_v3.get_conversation")

        with pytest.raises(HTTPException) as exc_info:
            await get_conversation_endpoint_handler(
                request=mocker.Mock(),
                conversation_id=INVALID_CONVERSATION_ID,
                auth=MOCK_AUTH,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        get_mock.assert_not_called()


class TestDeleteConversationEndpoint:
    """Test cases for the DELETE /v3/conversations/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_deleted(self, mocker: MockerFixture) -> None:
        """A removed conversation returns deleted=True."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.delete_conversation",
            return_value=True,
        )

        response = await delete_conversation_endpoint_handler(
            request=mocker.Mock(),
            conversation_id=VALID_CONVERSATION_ID,
            auth=MOCK_AUTH,
        )

        assert response.deleted is True
        assert response.conversation_id == VALID_CONVERSATION_ID

    @pytest.mark.asyncio
    async def test_not_deleted(self, mocker: MockerFixture) -> None:
        """A missing conversation returns deleted=False."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.delete_conversation",
            return_value=False,
        )

        response = await delete_conversation_endpoint_handler(
            request=mocker.Mock(),
            conversation_id=VALID_CONVERSATION_ID,
            auth=MOCK_AUTH,
        )

        assert response.deleted is False

    @pytest.mark.asyncio
    async def test_forbidden(self, mocker: MockerFixture) -> None:
        """Access denied becomes HTTP 403."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.delete_conversation",
            side_effect=ConversationAccessDeniedError(
                VALID_CONVERSATION_ID, MOCK_AUTH[0]
            ),
        )

        with pytest.raises(ConversationAccessDeniedError):
            await delete_conversation_endpoint_handler(
                request=mocker.Mock(),
                conversation_id=VALID_CONVERSATION_ID,
                auth=MOCK_AUTH,
            )


class TestUpdateConversationEndpoint:
    """Test cases for the PUT /v3/conversations/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_updated(self, mocker: MockerFixture) -> None:
        """A successful topic update returns success=True."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch("app.endpoints.conversations_v3.update_conversation_topic")

        response = await update_conversation_endpoint_handler(
            conversation_id=VALID_CONVERSATION_ID,
            update_request=ConversationUpdateRequest(topic_summary="new topic"),
            auth=MOCK_AUTH,
        )

        assert response.success is True
        assert response.conversation_id == VALID_CONVERSATION_ID

    @pytest.mark.asyncio
    async def test_not_found(self, mocker: MockerFixture) -> None:
        """Missing conversations become HTTP 404."""
        mock_authorization_resolvers(mocker)
        mocker.patch("app.endpoints.conversations_v3.check_configuration_loaded")
        mocker.patch(
            "app.endpoints.conversations_v3.update_conversation_topic",
            side_effect=ConversationNotFoundError(VALID_CONVERSATION_ID),
        )

        with pytest.raises(ConversationNotFoundError):
            await update_conversation_endpoint_handler(
                conversation_id=VALID_CONVERSATION_ID,
                update_request=ConversationUpdateRequest(topic_summary="new topic"),
                auth=MOCK_AUTH,
            )
