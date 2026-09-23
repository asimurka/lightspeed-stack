"""Demo catalog type classifiers: list-record hints, then PAI names, then id substrings."""

from collections.abc import Sequence
from typing import Final, Literal, get_args

from pydantic_ai.embeddings import KnownEmbeddingModelName
from pydantic_ai.models import KnownModelName

CatalogModelType = Literal["llm", "embedding", "rerank"]

_CHAT: Final[frozenset[str]] = frozenset(get_args(KnownModelName.__value__))
_EMBED: Final[frozenset[str]] = frozenset(get_args(KnownEmbeddingModelName.__value__))

_RESOURCE_PREFIXES: Final[tuple[str, ...]] = (
    "publishers/google/models/",
    "models/",
)

_RERANK_MARKERS: Final[tuple[str, ...]] = (
    "rerank",
    "re-rank",
    "cross-encoder",
    "crossencoder",
    "cross_encoder",
)

# `embed` already matches text-embedding, titan-embed, nomic-embed, cohere.embed, embedqa, …
_EMBED_MARKERS: Final[tuple[str, ...]] = (
    "embed",
    "ada-002",  # openai alias with no "embed" in the id
    "bge-",  # ST/vLLM Hub ids, e.g. BAAI/bge-large-en-v1.5
    "gte-",
    "e5-",  # includes multilingual-e5
    "slate",  # watsonx ibm/slate-*
    "sentence-transformers",  # org prefix; all-mpnet-base-v2 has no "embed"
)


def _bare(model_id: str) -> str:
    for prefix in _RESOURCE_PREFIXES:
        if model_id.startswith(prefix):
            return model_id.removeprefix(prefix)
    return model_id


def _from_name(model_id: str) -> CatalogModelType | None:
    lowered = _bare(model_id).lower()
    if any(m in lowered for m in _RERANK_MARKERS):
        return "rerank"
    if any(m in lowered for m in _EMBED_MARKERS):
        return "embedding"
    return None


def _from_pai(*prefixes: str, model_id: str) -> CatalogModelType | None:
    bare = _bare(model_id)
    for prefix in prefixes:
        key = f"{prefix}:{bare}"
        if key in _EMBED:
            return "embedding"
        if key in _CHAT:
            return "llm"
    return None


def classify_openai_model(model_id: str) -> CatalogModelType:
    """No type on OpenAI list rows. PAI openai: names, then id substrings."""
    return (
        _from_pai("openai", "openai-chat", model_id=model_id)
        or _from_name(model_id)
        or "llm"
    )


def classify_azure_model(
    model_id: str,
    *,
    base_model: str | None = None,
) -> CatalogModelType:
    """List id is often a deployment name. Prefer ARM/deployments ``model`` if passed."""
    for candidate in (base_model, model_id):
        if not candidate:
            continue
        typed = _from_pai("openai", model_id=candidate) or _from_name(candidate)
        if typed:
            return typed
    return "llm"


def classify_vllm_model(model_id: str) -> CatalogModelType:
    """OpenAI-compat list has no type. Name only (no PAI vllm: catalog)."""
    return _from_name(model_id) or "llm"


def classify_watsonx_model(
    model_id: str,
    *,
    functions: Sequence[str] | None = None,
) -> CatalogModelType:
    """OpenAI-compat list is ids only. Type from foundation-spec ``functions`` when given."""
    ids = {f.lower() for f in (functions or [])}
    if "embedding" in ids or "embed" in ids:
        return "embedding"
    if "rerank" in ids:
        return "rerank"
    return _from_name(model_id) or "llm"


def classify_vertexai_model(
    model_id: str,
    *,
    supported_actions: Sequence[str] | None = None,
) -> CatalogModelType:
    """``supported_actions`` on google-genai list rows: embedContent vs generateContent."""
    actions = {a.replace("_", "").lower() for a in (supported_actions or [])}
    if "embedcontent" in actions:
        return "embedding"
    if "generatecontent" in actions:
        return "llm"
    return (
        _from_pai("google-cloud", "google", model_id=model_id)
        or _from_name(model_id)
        or "llm"
    )


def classify_bedrock_model(
    model_id: str,
    *,
    output_modalities: Sequence[str] | None = None,
) -> CatalogModelType:
    """``outputModalities`` on ListFoundationModels (not the chat runtime list)."""
    mods = {m.upper() for m in (output_modalities or [])}
    if "EMBEDDING" in mods:
        return "embedding"
    if "TEXT" in mods:
        return "llm"
    return _from_pai("bedrock", model_id=model_id) or _from_name(model_id) or "llm"


def classify_sentence_transformers_model(model_id: str) -> CatalogModelType:
    """No PAI ST catalog. Name heuristic; default embedding (never llm)."""
    return _from_name(model_id) or "embedding"
