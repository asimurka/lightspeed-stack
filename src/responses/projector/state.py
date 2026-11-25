"""In-flight output item tracked by the OpenResponses projector."""

from dataclasses import dataclass, field
from typing import Literal, Optional

from responses.models.content import ResponseAnnotation
from responses.models.items import ResponseOutput
from responses.projector.classify import ProjectedToolKind


@dataclass
class OpenItem:  # pylint: disable=too-many-instance-attributes
    """Mutable projection state for one output item still in flight."""

    output_index: int
    item: ResponseOutput
    kind: ProjectedToolKind | Literal["message", "reasoning"]
    tool_call_id: Optional[str] = None
    hidden: bool = False
    arguments: str = ""
    text: str = ""
    annotations: list[ResponseAnnotation] = field(default_factory=list)
    content_index: int = 0
    done: bool = False
