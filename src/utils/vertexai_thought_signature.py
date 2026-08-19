"""Workaround for Gemini 3 thought_signature loss in OGX Vertex converters.

OGX converts Gemini responses to OpenAI-shaped assistant messages and rebuilds
Gemini history without ``thought_signature`` on ``function_call`` parts. Gemini 3
models reject the follow-up request with HTTP 400.

Google documents a last-resort sentinel for reconstructed history:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thought-signatures
"""

from __future__ import annotations

from typing import Any

from log import get_logger

logger = get_logger(__name__)

# Documented escape hatch when the real signature cannot be round-tripped.
SKIP_THOUGHT_SIGNATURE_VALIDATOR: str = "skip_thought_signature_validator"

_PATCH_APPLIED_ATTR = "_lcs_thought_signature_patch_applied"


def _inject_thought_signature_sentinel(content: dict[str, Any]) -> dict[str, Any]:
    """Add the skip sentinel to reconstructed function-call parts when missing.

    Parameters:
        content: Gemini ``Content``-like dict with ``parts``.

    Returns:
        The same dict with sentinel values injected where needed.
    """
    parts = content.get("parts")
    if not isinstance(parts, list):
        return content

    for part in parts:
        if not isinstance(part, dict):
            continue
        if "function_call" in part and "thought_signature" not in part:
            part["thought_signature"] = SKIP_THOUGHT_SIGNATURE_VALIDATOR

    return content


def apply_vertexai_thought_signature_workaround() -> bool:
    """Patch OGX Vertex assistant-message conversion to inject thought signatures.

    The patch is idempotent and safe to call multiple times (e.g. per uvicorn worker).

    Returns:
        True when the patch was applied or was already present, False when OGX
        Vertex converters are unavailable.
    """
    # pylint: disable=import-outside-toplevel,protected-access
    try:
        from ogx.providers.remote.inference.vertexai import (
            converters as vertex_converters,
        )
    except ImportError:
        logger.debug(
            "OGX Vertex converters unavailable; thought_signature workaround skipped"
        )
        return False

    if getattr(vertex_converters, _PATCH_APPLIED_ATTR, False):
        return True

    original_convert = vertex_converters._convert_assistant_message

    def _convert_assistant_message_with_sentinel(
        msg: dict[str, Any],
    ) -> dict[str, Any] | None:
        converted = original_convert(msg)
        if converted is None:
            return None
        return _inject_thought_signature_sentinel(converted)

    vertex_converters._convert_assistant_message = (
        _convert_assistant_message_with_sentinel
    )
    setattr(vertex_converters, _PATCH_APPLIED_ATTR, True)
    logger.info(
        "Applied Vertex AI thought_signature workaround (%s on reconstructed function calls)",
        SKIP_THOUGHT_SIGNATURE_VALIDATOR,
    )
    return True
