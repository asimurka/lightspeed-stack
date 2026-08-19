"""Workaround for Vertex AI rejecting OGX-mapped OpenAI ``service_tier`` values.

After the first Responses turn, OGX records ``service_tier="default"`` when the
provider did not return a tier. The Vertex adapter then maps that to Gemini
``"standard"`` on the next ``generateContent`` call (the MCP/tool follow-up).

Vertex AI's protobuf ``ServiceTier`` enum does not accept the lowercase SDK
string ``"standard"``, so the continuation request fails with HTTP 400. The
first turn already succeeded with the field omitted; this patch keeps that
behavior for every turn.
"""

from __future__ import annotations

from log import get_logger

logger = get_logger(__name__)

_PATCH_APPLIED_ATTR = "_lcs_service_tier_patch_applied"


def _omit_vertex_service_tier(_service_tier: str | None) -> None:
    """Drop OpenAI service-tier values so they are not sent to Vertex AI.

    Parameters:
        _service_tier: OpenAI ``service_tier`` from the chat-completions request.

    Returns:
        Always ``None`` so ``GenerateContentConfig.service_tier`` is omitted.
    """
    return None


def apply_vertexai_service_tier_workaround() -> bool:
    """Patch OGX Vertex chat config so invalid ``service_tier`` values are omitted.

    The patch is idempotent and safe to call multiple times (e.g. per uvicorn worker).

    Returns:
        True when the patch was applied or was already present, False when the
        OGX Vertex adapter is unavailable.
    """
    # pylint: disable=import-outside-toplevel,protected-access
    try:
        from ogx.providers.remote.inference.vertexai.vertexai import (
            VertexAIInferenceAdapter,
        )
    except ImportError:
        logger.debug("OGX Vertex adapter unavailable; service_tier workaround skipped")
        return False

    if getattr(VertexAIInferenceAdapter, _PATCH_APPLIED_ATTR, False):
        return True

    VertexAIInferenceAdapter._convert_service_tier = staticmethod(  # type: ignore[method-assign]
        _omit_vertex_service_tier
    )
    setattr(VertexAIInferenceAdapter, _PATCH_APPLIED_ATTR, True)
    logger.info(
        "Applied Vertex AI service_tier workaround (omit mapped values such as 'standard')"
    )
    return True
