"""Build OpenResponses refusal item events for blocked runs."""

from typing import Final

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
    """Build an assistant message whose content is a refusal part.

    Args:
        item_id: Public id for the output item.
        text: Refusal text shown to the client.
        status: Item status (``in_progress`` or ``completed``).

    Returns:
        Assistant message wrapping a ``refusal`` content part.

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
    """Events that open, stream, and close a refusal message item.

    Args:
        response_id: Parent response id.
        item: Completed refusal message.
        output_index: Index of the item in ``output``.
        text: Refusal text.

    Returns:
        OpenResponses events for the refusal item, without sequence numbers.

    """
    item_id = item.id or ""
    part = RefusalPart(refusal=text)
    return [
        ResponseOutputItemAddedEvent(
            response_id=response_id,
            item=item,
            output_index=output_index,
            sequence_number=0,
        ),
        ResponseContentPartAddedEvent(
            content_index=0,
            response_id=response_id,
            item_id=item_id,
            output_index=output_index,
            part=part,
            sequence_number=0,
        ),
        ResponseRefusalDeltaEvent(
            content_index=0,
            delta=text,
            item_id=item_id,
            output_index=output_index,
            sequence_number=0,
        ),
        ResponseRefusalDoneEvent(
            content_index=0,
            refusal=text,
            item_id=item_id,
            output_index=output_index,
            sequence_number=0,
        ),
        ResponseContentPartDoneEvent(
            content_index=0,
            response_id=response_id,
            item_id=item_id,
            output_index=output_index,
            part=part,
            sequence_number=0,
        ),
        ResponseOutputItemDoneEvent(
            response_id=response_id,
            item=item,
            output_index=output_index,
            sequence_number=0,
        ),
    ]
