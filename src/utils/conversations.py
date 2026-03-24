"""Utilities for conversations."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from llama_stack_api import OpenAIResponseMessage, OpenAIResponseOutput
from llama_stack_client import APIConnectionError, APIStatusError, AsyncLlamaStackClient
from llama_stack_client.types.conversations.item_create_params import Item
from llama_stack_client.types.conversations.item_list_response import (
    ItemListResponse,
)
from llama_stack_client.types.conversations.item_list_response import (
    OpenAIResponseMessageOutput as MessageOutput,
)

from models.database.conversations import UserTurn
from models.responses import (
    ConversationTurn,
    InternalServerErrorResponse,
    Message,
    ServiceUnavailableResponse,
)
from utils.tool_handlers import dispatch_response_item
from utils.types import ResponseInput, ResponseItem, ToolCallSummary, ToolResultSummary


def _extract_text_from_content(content: str | list[Any]) -> str:
    """Extract text content from message content.

    Args:
        content: The content field from a message (can be str or list)

    Returns:
        Extracted text content as a string
    """
    if isinstance(content, str):
        return content

    text_fragments: list[str] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                text_fragments.append(part)
                continue
            text_value = getattr(part, "text", None)
            if text_value:
                text_fragments.append(text_value)
                continue
            refusal = getattr(part, "refusal", None)
            if refusal:
                text_fragments.append(refusal)
                continue
            if isinstance(part, dict):
                dict_text = part.get("text") or part.get("refusal")
                if dict_text:
                    text_fragments.append(str(dict_text))

    return "".join(text_fragments)


def _parse_message_item(item: MessageOutput) -> Message:
    """Parse a message item into a Message object.

    Args:
        item: The message item from Conversations API

    Returns:
        Message object with extracted content and type (user or assistant)
    """
    content_text = _extract_text_from_content(item.content)
    message_type = item.role
    return Message(content=content_text, type=message_type, referenced_documents=None)


def _create_dummy_turn_metadata(started_at: datetime) -> UserTurn:
    """Create a dummy UserTurn instance for legacy conversations without metadata.

    Args:
        started_at: Timestamp to use for started_at and completed_at (conversation created_at)

    Returns:
        UserTurn instance with default values (N/A for provider/model, provided timestamp)
        for legacy conversations that don't have stored turn metadata.
    """
    # Create a UserTurn instance with default values for legacy conversations
    # Note: conversation_id and turn_number are not used, so we use placeholder values
    return UserTurn(
        conversation_id="",
        turn_number=0,
        started_at=started_at,
        completed_at=started_at,
        provider="N/A",
        model="N/A",
    )


def _create_turn_from_db_metadata(
    turn_metadata: UserTurn,
    messages: list[Message],
    tool_calls: list[ToolCallSummary],
    tool_results: list[ToolResultSummary],
) -> ConversationTurn:
    """Create a ConversationTurn from database metadata and accumulated items.

    Args:
        turn_metadata: Database UserTurn object with metadata
        messages: List of messages for this turn
        tool_calls: List of tool calls for this turn
        tool_results: List of tool results for this turn

    Returns:
        ConversationTurn object with all metadata populated
    """
    started_at = turn_metadata.started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    completed_at = turn_metadata.completed_at.astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return ConversationTurn(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        provider=turn_metadata.provider,
        model=turn_metadata.model,
        started_at=started_at,
        completed_at=completed_at,
    )


def _group_items_into_turns(
    items: list[ItemListResponse],
) -> list[list[ItemListResponse]]:
    """Group conversation items into turns.

    Each turn starts with a user message. All subsequent messages and tool items
    belong to that turn until the next user message.

    Args:
        items: Conversation items list from Conversations API, oldest first

    Returns:
        List of turns, where each turn is a list of items belonging to that turn
    """
    turns: list[list[ItemListResponse]] = []
    current_turn_items: list[ItemListResponse] = []

    for item in items:
        item_type = getattr(item, "type", None)

        # User message marks the beginning of a new turn
        if item_type == "message":
            message_item = cast(MessageOutput, item)
            if message_item.role == "user":
                # If we have accumulated items, finish the previous turn
                if current_turn_items:
                    turns.append(current_turn_items)
                    current_turn_items = []

                # Start new turn with this user message
                current_turn_items = [item]
            else:
                # Add non-user message to current turn
                current_turn_items.append(item)
        else:
            # Add tool-related items to current turn
            current_turn_items.append(item)

    # Add final turn if there are items
    if current_turn_items:
        turns.append(current_turn_items)

    return turns


def _process_turn_items(
    turn_items: list[ItemListResponse],
) -> tuple[list[Message], list[ToolCallSummary], list[ToolResultSummary]]:
    """Process items from a single turn into messages, tool calls, and tool results.

    Args:
        turn_items: List of items belonging to a single turn

    Returns:
        Tuple of (messages, tool_calls, tool_results)
    """
    messages: list[Message] = []
    tool_calls: list[ToolCallSummary] = []
    tool_results: list[ToolResultSummary] = []

    for item in turn_items:
        item_type = getattr(item, "type", None)

        if item_type == "message":
            message_item = cast(MessageOutput, item)
            message = _parse_message_item(message_item)
            messages.append(message)
        else:
            tool_call, tool_result = dispatch_response_item(cast(ResponseItem, item))
            if tool_call is not None:
                tool_calls.append(tool_call)
            if tool_result is not None:
                tool_results.append(tool_result)

    return messages, tool_calls, tool_results


def build_conversation_turns_from_items(
    items: list[ItemListResponse],
    turns_metadata: list[UserTurn],
    conversation_start_time: datetime,
) -> list[ConversationTurn]:
    """Build conversation turns from Conversations API items and turns metadata.

    Args:
        items: Conversation items list from Conversations API, oldest first
        turns_metadata: List of UserTurn database objects ordered by turn_number.
            Can be empty for legacy conversations without stored metadata.
            For extended legacy conversations, only the newer turns have metadata.
        conversation_start_time: Timestamp to use for dummy metadata in legacy conversations.
            Typically the conversation's created_at timestamp.

    Returns:
        List of ConversationTurn objects, oldest first
    """
    # Group items into turns first
    turn_items_list = _group_items_into_turns(items)

    # Calculate how many legacy turns don't have metadata
    total_turns = len(turn_items_list)
    legacy_turns_count = total_turns - len(turns_metadata)

    # Process each turn with its corresponding metadata
    chat_history: list[ConversationTurn] = []
    for turn_index, turn_items in enumerate(turn_items_list):
        # Process items into messages, tool calls, and tool results
        messages, tool_calls, tool_results = _process_turn_items(turn_items)

        # Select appropriate metadata for this turn
        if turn_index < legacy_turns_count:
            turn_metadata = _create_dummy_turn_metadata(conversation_start_time)
        else:
            metadata_index = turn_index - legacy_turns_count
            turn_metadata = turns_metadata[metadata_index]

        # Create ConversationTurn from metadata and processed items
        chat_history.append(
            _create_turn_from_db_metadata(
                turn_metadata,
                messages,
                tool_calls,
                tool_results,
            )
        )

    return chat_history


async def append_turn_items_to_conversation(
    client: AsyncLlamaStackClient,
    conversation_id: str,
    user_input: ResponseInput,
    llm_output: Sequence[OpenAIResponseOutput],
) -> None:
    """
    Append a turn (user input + LLM output) to a conversation in LLS database.

    Args:
        client: The Llama Stack client.
        conversation_id: The Llama Stack conversation ID.
        user_input: User input text or list of ResponseItem.
        llm_output: Output from the LLM: a list of OpenAIResponseOutput.
    """
    if isinstance(user_input, str):
        user_message = OpenAIResponseMessage(
            role="user",
            content=user_input,
        )
        user_items = [user_message.model_dump()]
    else:
        user_items = [item.model_dump() for item in user_input]

    output_items = [item.model_dump() for item in llm_output]

    items = user_items + output_items
    try:
        await client.conversations.items.create(
            conversation_id,
            items=cast(list[Item], items),
        )
    except APIConnectionError as e:
        error_response = ServiceUnavailableResponse(
            backend_name="Llama Stack",
            cause=str(e),
        )
        raise HTTPException(**error_response.model_dump()) from e
    except APIStatusError as e:
        error_response = InternalServerErrorResponse.generic()
        raise HTTPException(**error_response.model_dump()) from e


async def get_all_conversation_items(
    client: AsyncLlamaStackClient,
    conversation_id_llama_stack: str,
) -> list[ItemListResponse]:
    """Fetch all items for a conversation (Conversations API), paginating as needed.

    Args:
        client: Llama Stack client.
        conversation_id_llama_stack: Conversation ID in Llama Stack format.

    Returns:
        List of all items in the conversation, oldest first.
    """
    try:
        paginator = client.conversations.items.list(
            conversation_id=conversation_id_llama_stack,
            order="asc",
        )
        first_page = await paginator
        items: list[ItemListResponse] = list(first_page.data or [])
        page = first_page
        while page.has_next_page():
            page = await page.get_next_page()
            items.extend(page.data or [])
        return items
    except APIConnectionError as e:
        error_response = ServiceUnavailableResponse(
            backend_name="Llama Stack",
            cause=str(e),
        )
        raise HTTPException(**error_response.model_dump()) from e
    except APIStatusError as e:
        error_response = InternalServerErrorResponse.generic()
        raise HTTPException(**error_response.model_dump()) from e
