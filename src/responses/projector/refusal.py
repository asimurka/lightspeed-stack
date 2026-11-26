"""OpenResponses stream events for policy refusals."""

from typing import Final, cast

from responses.models.content import RefusalPart
from responses.models.events import (
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseRefusalDeltaEvent,
    ResponseRefusalDoneEvent,
    ResponseStreamEvent,
)
from responses.models.items import ResponseMessage

DEFAULT_REFUSAL_TEXT: Final[str] = (
    "I cannot process this request due to policy restrictions."
)


def refusal_message(item_id: str, text: str, status: str) -> ResponseMessage:
    """Build an assistant message that carries refusal content.

    Args:
        item_id: Output item id.
        text: Refusal text.
        status: Item status such as in_progress or completed.

    Returns:
        Assistant message with a refusal content part.

    """
    return ResponseMessage(
        type="message",
        role="assistant",
        content=[RefusalPart(refusal=text)],
        id=item_id,
        status=status,
    )


def refusal_stream_events(
    *,
    response_id: str,
    item: ResponseMessage,
    output_index: int,
    text: str,
) -> list[ResponseStreamEvent]:
    """Build stream events that open, stream, and close a refusal message.

    Args:
        response_id: Parent response id.
        item: Completed refusal message.
        output_index: Index of the item in output.
        text: Refusal text.

    Returns:
        OpenResponses events; sequence numbers are assigned in _emit.

    """
    item_id = cast(str, item.id)
    part = RefusalPart(refusal=text)
    return [
        ResponseOutputItemAddedEvent(
            response_id=response_id,
            item=item,
            output_index=output_index,
        ),
        ResponseContentPartAddedEvent(
            content_index=0,
            response_id=response_id,
            item_id=item_id,
            output_index=output_index,
            part=part,
        ),
        ResponseRefusalDeltaEvent(
            content_index=0,
            delta=text,
            item_id=item_id,
            output_index=output_index,
        ),
        ResponseRefusalDoneEvent(
            content_index=0,
            refusal=text,
            item_id=item_id,
            output_index=output_index,
        ),
        ResponseContentPartDoneEvent(
            content_index=0,
            response_id=response_id,
            item_id=item_id,
            output_index=output_index,
            part=part,
        ),
        ResponseOutputItemDoneEvent(
            response_id=response_id,
            item=item,
            output_index=output_index,
        ),
    ]
