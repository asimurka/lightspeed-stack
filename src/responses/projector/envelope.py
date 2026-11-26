"""Create the live OpenResponses envelope at the start of a run."""

import time
from typing import Any, Optional

from responses.models.response import ResponseObject


def initial_response(
    *,
    response_id: str,
    model: str,
    created_at: Optional[int] = None,
    conversation: Optional[str] = None,
    **echo: Any,
) -> ResponseObject:
    """Build an in-progress response with empty output and terminal fields.

    Args:
        response_id: Public response id.
        model: Model name echoed on the response.
        created_at: Creation time in Unix seconds; defaults to now.
        conversation: Optional conversation id.
        **echo: Additional request fields copied onto the response.

    Returns:
        Mutable response with empty output, output_text, and quotas.

    """
    return ResponseObject(
        id=response_id,
        model=model,
        created_at=created_at if created_at is not None else int(time.time()),
        conversation=conversation,
        status="in_progress",
        output=[],
        available_quotas={},
        output_text="",
        **echo,
    )
