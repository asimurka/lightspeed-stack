"""Handler for REST API calls to manage agentic display-history conversations."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from opentelemetry import trace

from authentication import get_auth_dependency
from authorization.middleware import authorize
from configuration import configuration
from conversations.display_history.persistence.facade.conversation import (
    delete_conversation,
    get_conversation,
    list_conversations,
    update_conversation_topic,
)
from log import get_logger
from models.api.requests import ConversationUpdateRequest
from models.api.responses.constants import UNAUTHORIZED_OPENAPI_EXAMPLES
from models.api.responses.error import (
    BadRequestResponse,
    ForbiddenResponse,
    InternalServerErrorResponse,
    NotFoundResponse,
    ServiceUnavailableResponse,
    UnauthorizedResponse,
)
from models.api.responses.successful import (
    ConversationDeleteResponse,
    ConversationResponseV3,
    ConversationsListResponseV3,
    ConversationUpdateResponse,
)
from models.config import Action
from utils.endpoints import check_configuration_loaded
from utils.suid import check_suid
from utils.types import Responses

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter(tags=["conversations_v3"])


conversation_get_responses: Responses = {
    200: ConversationResponseV3.openapi_response(),
    400: BadRequestResponse.openapi_response(examples=["conversation_id"]),
    401: UnauthorizedResponse.openapi_response(examples=UNAUTHORIZED_OPENAPI_EXAMPLES),
    403: ForbiddenResponse.openapi_response(examples=["conversation read", "endpoint"]),
    404: NotFoundResponse.openapi_response(examples=["conversation"]),
    500: InternalServerErrorResponse.openapi_response(
        examples=["database", "configuration"]
    ),
    503: ServiceUnavailableResponse.openapi_response(examples=["kubernetes api"]),
}

conversation_delete_responses: Responses = {
    200: ConversationDeleteResponse.openapi_response(),
    400: BadRequestResponse.openapi_response(examples=["conversation_id"]),
    401: UnauthorizedResponse.openapi_response(examples=UNAUTHORIZED_OPENAPI_EXAMPLES),
    403: ForbiddenResponse.openapi_response(
        examples=["conversation delete", "endpoint"]
    ),
    500: InternalServerErrorResponse.openapi_response(
        examples=["database", "configuration"]
    ),
    503: ServiceUnavailableResponse.openapi_response(examples=["kubernetes api"]),
}

conversations_list_responses: Responses = {
    200: ConversationsListResponseV3.openapi_response(),
    401: UnauthorizedResponse.openapi_response(examples=UNAUTHORIZED_OPENAPI_EXAMPLES),
    403: ForbiddenResponse.openapi_response(examples=["endpoint"]),
    500: InternalServerErrorResponse.openapi_response(
        examples=["database", "configuration"]
    ),
    503: ServiceUnavailableResponse.openapi_response(examples=["kubernetes api"]),
}

conversation_update_responses: Responses = {
    200: ConversationUpdateResponse.openapi_response(),
    400: BadRequestResponse.openapi_response(examples=["conversation_id"]),
    401: UnauthorizedResponse.openapi_response(examples=UNAUTHORIZED_OPENAPI_EXAMPLES),
    403: ForbiddenResponse.openapi_response(examples=["endpoint"]),
    404: NotFoundResponse.openapi_response(examples=["conversation"]),
    500: InternalServerErrorResponse.openapi_response(
        examples=["database", "configuration"]
    ),
    503: ServiceUnavailableResponse.openapi_response(examples=["kubernetes api"]),
}


@router.get("/conversations", responses=conversations_list_responses)
@authorize(Action.LIST_CONVERSATIONS)
async def get_conversations_list_endpoint_handler(
    request: Request,  # pylint: disable=unused-argument
    auth: Any = Depends(get_auth_dependency()),
) -> ConversationsListResponseV3:
    """Handle request to retrieve all conversations for the authenticated user."""
    with tracer.start_as_current_span("conversations_v3.list") as span:
        check_configuration_loaded(configuration)
        user_id = auth[0]
        others_allowed = auth[2]
        logger.info("Retrieving conversations for user %s", user_id)
        conversations = list_conversations(user_id, others_allowed)
        span.set_attribute("conversations.count", len(conversations))
        return ConversationsListResponseV3(conversations=conversations)


@router.get(
    "/conversations/{conversation_id}",
    responses=conversation_get_responses,
)
@authorize(Action.GET_CONVERSATION)
async def get_conversation_endpoint_handler(
    request: Request,  # pylint: disable=unused-argument
    conversation_id: str,
    auth: Any = Depends(get_auth_dependency()),
) -> ConversationResponseV3:
    """Handle request to retrieve a conversation identified by its ID."""
    with tracer.start_as_current_span("conversations_v3.get") as span:
        check_configuration_loaded(configuration)
        check_valid_conversation_id(conversation_id)
        user_id = auth[0]
        others_allowed = auth[2]
        logger.info("Retrieving conversation %s for user %s", conversation_id, user_id)
        conversation = get_conversation(conversation_id, user_id, others_allowed)
        span.set_attribute("conversations.found", True)
        span.set_attribute("conversations.turns.count", len(conversation.chat_history))
        return ConversationResponseV3.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}", responses=conversation_delete_responses
)
@authorize(Action.DELETE_CONVERSATION)
async def delete_conversation_endpoint_handler(
    request: Request,  # pylint: disable=unused-argument
    conversation_id: str,
    auth: Any = Depends(get_auth_dependency()),
) -> ConversationDeleteResponse:
    """Handle request to delete a conversation by ID."""
    with tracer.start_as_current_span("conversations_v3.delete") as span:
        check_configuration_loaded(configuration)
        check_valid_conversation_id(conversation_id)
        user_id = auth[0]
        others_allowed = auth[2]
        logger.info("Deleting conversation %s for user %s", conversation_id, user_id)
        deleted = delete_conversation(conversation_id, user_id, others_allowed)
        span.set_attribute("conversations.deleted", deleted)
        return ConversationDeleteResponse(
            deleted=deleted, conversation_id=conversation_id
        )


@router.put("/conversations/{conversation_id}", responses=conversation_update_responses)
@authorize(Action.UPDATE_CONVERSATION)
async def update_conversation_endpoint_handler(
    conversation_id: str,
    update_request: ConversationUpdateRequest,
    auth: Any = Depends(get_auth_dependency()),
) -> ConversationUpdateResponse:
    """Handle request to update a conversation topic summary by ID."""
    with tracer.start_as_current_span("conversations_v3.update") as span:
        check_configuration_loaded(configuration)
        check_valid_conversation_id(conversation_id)
        user_id = auth[0]
        others_allowed = auth[2]
        logger.info(
            "Updating topic summary for conversation %s for user %s",
            conversation_id,
            user_id,
        )
        update_conversation_topic(
            conversation_id,
            user_id,
            others_allowed,
            update_request.topic_summary,
        )
        span.set_attribute("conversations.updated", True)
        return ConversationUpdateResponse(
            conversation_id=conversation_id,
            success=True,
            message="Topic summary updated successfully",
        )


def check_valid_conversation_id(conversation_id: str) -> None:
    """Check validity of conversation ID format."""
    if not check_suid(conversation_id):
        logger.error("Invalid conversation ID format: %s", conversation_id)
        response = BadRequestResponse(
            resource="conversation", resource_id=conversation_id
        )
        raise HTTPException(**response.model_dump())
