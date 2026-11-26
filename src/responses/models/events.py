"""Streaming events emitted while a response is generated."""

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

from responses.models.content import (
    ResponseAnnotation,
    StreamContentPart,
    StreamReasoningSummaryPart,
    TokenLogProb,
)
from responses.models.items import ResponseOutput
from responses.models.response import ResponseObject


class ResponseStreamEventBase(BaseModel):
    """Fields shared by every OpenResponses stream event."""

    sequence_number: int = Field(
        default=0,
        description="Monotonic SSE index. The projector assigns this before yield.",
    )


class ResponseCreatedEvent(ResponseStreamEventBase):
    """Emitted when a response is created."""

    type: Literal["response.created"] = "response.created"
    response: ResponseObject


class ResponseInProgressEvent(ResponseStreamEventBase):
    """Emitted while the response is still running."""

    type: Literal["response.in_progress"] = "response.in_progress"
    response: ResponseObject


class ResponseCompletedEvent(ResponseStreamEventBase):
    """Emitted when the response finishes successfully."""

    type: Literal["response.completed"] = "response.completed"
    response: ResponseObject


class ResponseIncompleteEvent(ResponseStreamEventBase):
    """Emitted when the response stops before it finishes."""

    type: Literal["response.incomplete"] = "response.incomplete"
    response: ResponseObject


class ResponseFailedEvent(ResponseStreamEventBase):
    """Emitted when the response fails after it has started."""

    type: Literal["response.failed"] = "response.failed"
    response: ResponseObject


class ResponseErrorEvent(ResponseStreamEventBase):
    """Emitted when a transport or infrastructure error occurs."""

    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None
    param: Optional[str] = None


class ResponseOutputItemAddedEvent(ResponseStreamEventBase):
    """Emitted when an output item is added."""

    type: Literal["response.output_item.added"] = "response.output_item.added"
    response_id: str
    item: ResponseOutput
    output_index: int


class ResponseOutputItemDoneEvent(ResponseStreamEventBase):
    """Emitted when an output item is complete."""

    type: Literal["response.output_item.done"] = "response.output_item.done"
    response_id: str
    item: ResponseOutput
    output_index: int


class ResponseOutputTextDeltaEvent(ResponseStreamEventBase):
    """Emitted when more output text is produced."""

    type: Literal["response.output_text.delta"] = "response.output_text.delta"
    content_index: int
    delta: str
    item_id: str
    output_index: int
    logprobs: Optional[list[TokenLogProb]] = None


class ResponseOutputTextDoneEvent(ResponseStreamEventBase):
    """Emitted when output text is complete."""

    type: Literal["response.output_text.done"] = "response.output_text.done"
    content_index: int
    text: str
    item_id: str
    output_index: int


class ResponseFunctionCallArgumentsDeltaEvent(ResponseStreamEventBase):
    """Emitted when more function-call arguments are produced."""

    type: Literal["response.function_call_arguments.delta"] = (
        "response.function_call_arguments.delta"
    )
    delta: str
    item_id: str
    output_index: int


class ResponseFunctionCallArgumentsDoneEvent(ResponseStreamEventBase):
    """Emitted when function-call arguments are complete."""

    type: Literal["response.function_call_arguments.done"] = (
        "response.function_call_arguments.done"
    )
    arguments: str
    item_id: str
    output_index: int


class ResponseMcpListToolsInProgressEvent(ResponseStreamEventBase):
    """Emitted while MCP tools are being listed."""

    type: Literal["response.mcp_list_tools.in_progress"] = (
        "response.mcp_list_tools.in_progress"
    )
    item_id: str
    output_index: int


class ResponseMcpListToolsFailedEvent(ResponseStreamEventBase):
    """Emitted when listing MCP tools fails."""

    type: Literal["response.mcp_list_tools.failed"] = "response.mcp_list_tools.failed"
    item_id: str
    output_index: int


class ResponseMcpListToolsCompletedEvent(ResponseStreamEventBase):
    """Emitted when listing MCP tools finishes."""

    type: Literal["response.mcp_list_tools.completed"] = (
        "response.mcp_list_tools.completed"
    )
    item_id: str
    output_index: int


class ResponseMcpCallArgumentsDeltaEvent(ResponseStreamEventBase):
    """Emitted when more MCP call arguments are produced."""

    type: Literal["response.mcp_call_arguments.delta"] = (
        "response.mcp_call_arguments.delta"
    )
    delta: str
    item_id: str
    output_index: int


class ResponseMcpCallArgumentsDoneEvent(ResponseStreamEventBase):
    """Emitted when MCP call arguments are complete."""

    type: Literal["response.mcp_call_arguments.done"] = (
        "response.mcp_call_arguments.done"
    )
    arguments: str
    item_id: str
    output_index: int


class ResponseMcpCallInProgressEvent(ResponseStreamEventBase):
    """Emitted while an MCP tool call is running."""

    type: Literal["response.mcp_call.in_progress"] = "response.mcp_call.in_progress"
    item_id: str
    output_index: int


class ResponseMcpCallFailedEvent(ResponseStreamEventBase):
    """Emitted when an MCP tool call fails."""

    type: Literal["response.mcp_call.failed"] = "response.mcp_call.failed"
    item_id: str
    output_index: int


class ResponseMcpCallCompletedEvent(ResponseStreamEventBase):
    """Emitted when an MCP tool call finishes."""

    type: Literal["response.mcp_call.completed"] = "response.mcp_call.completed"
    item_id: str
    output_index: int


class ResponseContentPartAddedEvent(ResponseStreamEventBase):
    """Emitted when a content part is added."""

    type: Literal["response.content_part.added"] = "response.content_part.added"
    content_index: int
    response_id: str
    item_id: str
    output_index: int
    part: StreamContentPart


class ResponseContentPartDoneEvent(ResponseStreamEventBase):
    """Emitted when a content part is complete."""

    type: Literal["response.content_part.done"] = "response.content_part.done"
    content_index: int
    response_id: str
    item_id: str
    output_index: int
    part: StreamContentPart


class ResponseReasoningTextDeltaEvent(ResponseStreamEventBase):
    """Emitted when more reasoning text is produced."""

    type: Literal["response.reasoning_text.delta"] = "response.reasoning_text.delta"
    content_index: int
    delta: str
    item_id: str
    output_index: int


class ResponseReasoningTextDoneEvent(ResponseStreamEventBase):
    """Emitted when reasoning text is complete."""

    type: Literal["response.reasoning_text.done"] = "response.reasoning_text.done"
    content_index: int
    text: str
    item_id: str
    output_index: int


class ResponseReasoningSummaryPartAddedEvent(ResponseStreamEventBase):
    """Emitted when a reasoning summary part is added."""

    type: Literal["response.reasoning_summary_part.added"] = (
        "response.reasoning_summary_part.added"
    )
    item_id: str
    output_index: int
    part: StreamReasoningSummaryPart
    summary_index: int


class ResponseReasoningSummaryPartDoneEvent(ResponseStreamEventBase):
    """Emitted when a reasoning summary part is complete."""

    type: Literal["response.reasoning_summary_part.done"] = (
        "response.reasoning_summary_part.done"
    )
    item_id: str
    output_index: int
    part: StreamReasoningSummaryPart
    summary_index: int


class ResponseReasoningSummaryTextDeltaEvent(ResponseStreamEventBase):
    """Emitted when more reasoning summary text is produced."""

    type: Literal["response.reasoning_summary_text.delta"] = (
        "response.reasoning_summary_text.delta"
    )
    delta: str
    item_id: str
    output_index: int
    summary_index: int


class ResponseReasoningSummaryTextDoneEvent(ResponseStreamEventBase):
    """Emitted when reasoning summary text is complete."""

    type: Literal["response.reasoning_summary_text.done"] = (
        "response.reasoning_summary_text.done"
    )
    text: str
    item_id: str
    output_index: int
    summary_index: int


class ResponseRefusalDeltaEvent(ResponseStreamEventBase):
    """Emitted when more refusal text is produced."""

    type: Literal["response.refusal.delta"] = "response.refusal.delta"
    content_index: int
    delta: str
    item_id: str
    output_index: int


class ResponseRefusalDoneEvent(ResponseStreamEventBase):
    """Emitted when refusal text is complete."""

    type: Literal["response.refusal.done"] = "response.refusal.done"
    content_index: int
    refusal: str
    item_id: str
    output_index: int


class ResponseOutputTextAnnotationAddedEvent(ResponseStreamEventBase):
    """Emitted when a citation is added to output text."""

    type: Literal["response.output_text.annotation.added"] = (
        "response.output_text.annotation.added"
    )
    item_id: str
    output_index: int
    content_index: int
    annotation_index: int
    annotation: ResponseAnnotation


class ResponseFileSearchCallInProgressEvent(ResponseStreamEventBase):
    """Emitted when a file search starts."""

    type: Literal["response.file_search_call.in_progress"] = (
        "response.file_search_call.in_progress"
    )
    item_id: str
    output_index: int


class ResponseFileSearchCallSearchingEvent(ResponseStreamEventBase):
    """Emitted while file search is running."""

    type: Literal["response.file_search_call.searching"] = (
        "response.file_search_call.searching"
    )
    item_id: str
    output_index: int


class ResponseFileSearchCallCompletedEvent(ResponseStreamEventBase):
    """Emitted when a file search finishes."""

    type: Literal["response.file_search_call.completed"] = (
        "response.file_search_call.completed"
    )
    item_id: str
    output_index: int


ResponseStreamEvent = Annotated[
    ResponseCreatedEvent
    | ResponseInProgressEvent
    | ResponseOutputItemAddedEvent
    | ResponseOutputItemDoneEvent
    | ResponseOutputTextDeltaEvent
    | ResponseOutputTextDoneEvent
    | ResponseFunctionCallArgumentsDeltaEvent
    | ResponseFunctionCallArgumentsDoneEvent
    | ResponseMcpListToolsInProgressEvent
    | ResponseMcpListToolsFailedEvent
    | ResponseMcpListToolsCompletedEvent
    | ResponseMcpCallArgumentsDeltaEvent
    | ResponseMcpCallArgumentsDoneEvent
    | ResponseMcpCallInProgressEvent
    | ResponseMcpCallFailedEvent
    | ResponseMcpCallCompletedEvent
    | ResponseContentPartAddedEvent
    | ResponseContentPartDoneEvent
    | ResponseReasoningTextDeltaEvent
    | ResponseReasoningTextDoneEvent
    | ResponseReasoningSummaryPartAddedEvent
    | ResponseReasoningSummaryPartDoneEvent
    | ResponseReasoningSummaryTextDeltaEvent
    | ResponseReasoningSummaryTextDoneEvent
    | ResponseRefusalDeltaEvent
    | ResponseRefusalDoneEvent
    | ResponseOutputTextAnnotationAddedEvent
    | ResponseFileSearchCallInProgressEvent
    | ResponseFileSearchCallSearchingEvent
    | ResponseFileSearchCallCompletedEvent
    | ResponseIncompleteEvent
    | ResponseFailedEvent
    | ResponseCompletedEvent
    | ResponseErrorEvent,
    Field(discriminator="type"),
]
