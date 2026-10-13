"""Shared helpers for inference provider integrations."""

from __future__ import annotations

from typing import Any, get_args

from pydantic_ai.embeddings import KnownEmbeddingModelName
from pydantic_ai.models import KnownModelName

from providers.inference.types import ModelType


def _wire_ids_from_known_names(known_names: Any) -> frozenset[str]:
    """Collect wire model ids from a PAI known-name Literal alias.

    PAI entries look like ``openai:gpt-4o``; the provider prefix before the
    first colon is stripped so ids match OpenAI-compatible ``/models`` rows.
    """
    annotation = getattr(known_names, "__value__", known_names)
    return frozenset(
        name.split(":", 1)[-1] for name in get_args(annotation) if isinstance(name, str)
    )


KNOWN_LLM_IDS: frozenset[str] = _wire_ids_from_known_names(KnownModelName)
KNOWN_EMBEDDING_IDS: frozenset[str] = _wire_ids_from_known_names(
    KnownEmbeddingModelName
)


def infer_model_type(provider_model_id: str) -> ModelType:
    """Classify a wire model id using PAI known LLM and embedding names."""
    if provider_model_id in KNOWN_EMBEDDING_IDS:
        return "embedding"
    if provider_model_id in KNOWN_LLM_IDS:
        return "llm"
    return "llm"
