"""Unit tests for shared inference provider helpers."""

from providers.inference.utils import (
    KNOWN_EMBEDDING_IDS,
    KNOWN_LLM_IDS,
    infer_model_type,
)


def test_known_ids_include_openai_wire_ids() -> None:
    """PAI known-name tables are exposed as prefix-stripped wire ids."""
    assert "gpt-4o-mini" in KNOWN_LLM_IDS
    assert "text-embedding-3-small" in KNOWN_EMBEDDING_IDS
    assert "openai:gpt-4o-mini" not in KNOWN_LLM_IDS


def test_infer_model_type_known_embedding_else_llm() -> None:
    """Known embedding ids map to embedding; everything else is llm."""
    assert infer_model_type("text-embedding-3-small") == "embedding"
    assert infer_model_type("gpt-4o-mini") == "llm"
    assert infer_model_type("totally-custom-chat") == "llm"
