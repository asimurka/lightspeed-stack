"""Unit tests for the OpenAI inference provider."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from models.config import OpenAIInferenceProviderEntry
from providers.inference.catalog import CatalogModel
from providers.inference.errors import (
    ModelNotAvailableError,
    ModelTypeNotSupportedError,
)
from providers.inference.openai.provider import OpenAIInferenceProvider
from providers.inference.registry import PROVIDER_CLASSES
from providers.inference.types import ModelType
from providers.inference.utils import KNOWN_EMBEDDING_IDS, KNOWN_LLM_IDS


def _entry(**overrides: Any) -> OpenAIInferenceProviderEntry:
    """Build an OpenAI provider config entry."""
    payload: dict[str, Any] = {
        "type": "openai",
        "id": "openai",
        "config": {"api_key": "test-key", "base_url": "https://example.test/v1"},
    }
    payload.update(overrides)
    return OpenAIInferenceProviderEntry.model_validate(payload)


def _listed_model(model_id: str, *, owned_by: str = "openai") -> SimpleNamespace:
    """Build a fake OpenAI SDK model list row."""
    return SimpleNamespace(id=model_id, owned_by=owned_by)


@pytest.fixture(name="provider")
def provider_fixture() -> OpenAIInferenceProvider:
    """Create an uninitialized OpenAI provider."""
    return OpenAIInferenceProvider(_entry())


def test_provider_is_registered_as_openai() -> None:
    """Importing the package registers the OpenAI provider class."""
    assert PROVIDER_CLASSES["openai"] is OpenAIInferenceProvider


def test_build_provider_uses_config_api_key_and_base_url(
    provider: OpenAIInferenceProvider,
) -> None:
    """_build_provider forwards api_key and base_url into PAI OpenAIProvider."""
    pai_provider = provider._build_provider()  # pylint: disable=protected-access

    assert isinstance(pai_provider, OpenAIProvider)
    assert str(pai_provider.client.base_url).rstrip("/") == "https://example.test/v1"
    assert pai_provider.client.api_key == "test-key"


@pytest.mark.asyncio
async def test_discover_models_maps_openai_list_rows(
    provider: OpenAIInferenceProvider,
    mocker: Any,
) -> None:
    """Discovery maps /models rows into DiscoveredModel entries."""
    page = mocker.MagicMock()
    page.data = [
        _listed_model("gpt-4o-mini"),
        _listed_model("text-embedding-3-small", owned_by="openai"),
        _listed_model("custom-chat-model", owned_by="org"),
    ]
    mock_client = mocker.MagicMock()
    mock_client.models.list = mocker.AsyncMock(return_value=page)
    mock_pai = mocker.MagicMock(spec=OpenAIProvider)
    mock_pai.client = mock_client
    provider._provider = mock_pai  # pylint: disable=protected-access

    discovered = await provider._discover_models()  # pylint: disable=protected-access

    assert [model.provider_model_id for model in discovered] == [
        "gpt-4o-mini",
        "text-embedding-3-small",
        "custom-chat-model",
    ]
    assert discovered[0].model_type == "llm"
    assert discovered[1].model_type == "embedding"
    assert discovered[2].model_type == "llm"
    assert discovered[1].metadata == {}
    mock_client.models.list.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_initialize_skip_model_discovery_builds_catalog_from_allow_list(
    mocker: Any,
) -> None:
    """skip_model_discovery uses allow-list rows and still builds the PAI provider."""
    mocker.patch.object(
        OpenAIInferenceProvider,
        "_build_provider",
        return_value=mocker.MagicMock(spec=OpenAIProvider),
    )
    entry = _entry(
        skip_model_discovery=True,
        allowed_models=[
            {
                "name": "chat",
                "provider_model_id": "gpt-4o-mini",
                "model_type": "llm",
            },
            {
                "name": "embed",
                "provider_model_id": "text-embedding-3-small",
            },
        ],
    )
    provider = OpenAIInferenceProvider(entry)

    await provider.initialize()

    models = provider.list_catalog_models()
    assert [
        (model.name, model.provider_model_id, model.model_type) for model in models
    ] == [
        ("chat", "gpt-4o-mini", "llm"),
        ("embed", "text-embedding-3-small", "embedding"),
    ]


@pytest.mark.asyncio
async def test_initialize_intersects_discovered_models_with_allow_list(
    mocker: Any,
) -> None:
    """Allow-list keeps only discovered wire ids and applies local names."""
    page = mocker.MagicMock()
    page.data = [
        _listed_model("gpt-4o-mini"),
        _listed_model("text-embedding-3-small"),
        _listed_model("gpt-4o"),
    ]
    mock_client = mocker.MagicMock()
    mock_client.models.list = mocker.AsyncMock(return_value=page)
    mock_pai = mocker.MagicMock(spec=OpenAIProvider)
    mock_pai.client = mock_client
    mocker.patch.object(
        OpenAIInferenceProvider,
        "_build_provider",
        return_value=mock_pai,
    )
    entry = _entry(
        allowed_models=[
            {
                "name": "chat",
                "provider_model_id": "gpt-4o-mini",
            },
            {
                "name": "missing",
                "provider_model_id": "does-not-exist",
            },
        ]
    )
    provider = OpenAIInferenceProvider(entry)

    await provider.initialize()

    models = provider.list_catalog_models()
    assert len(models) == 1
    assert models[0].name == "chat"
    assert models[0].provider_model_id == "gpt-4o-mini"
    assert models[0].model_type == "llm"


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("gpt-4o-mini", "llm"),
        ("text-embedding-3-small", "embedding"),
        ("totally-custom-chat", "llm"),
    ],
)
def test_infer_model_type_known_names_else_llm(
    provider: OpenAIInferenceProvider,
    model_id: str,
    expected: ModelType,
) -> None:
    """Known embedding names map to embedding; everything else is llm."""
    assert "gpt-4o-mini" in KNOWN_LLM_IDS
    assert "text-embedding-3-small" in KNOWN_EMBEDDING_IDS

    inferred = provider._infer_model_type(model_id)  # pylint: disable=protected-access

    assert inferred == expected


def test_create_llm_and_embedding_use_catalog_wire_ids(
    provider: OpenAIInferenceProvider,
) -> None:
    """Creators pass provider_model_id into PAI model constructors."""
    pai = provider._build_provider()  # pylint: disable=protected-access
    provider._provider = pai  # pylint: disable=protected-access

    llm = provider._create_llm(  # pylint: disable=protected-access
        CatalogModel(
            name="chat",
            provider_model_id="gpt-4o-mini",
            model_type="llm",
        )
    )
    embedding = provider._create_embedding(  # pylint: disable=protected-access
        CatalogModel(
            name="embed",
            provider_model_id="text-embedding-3-small",
            model_type="embedding",
        )
    )

    assert isinstance(llm, OpenAIResponsesModel)
    assert llm.model_name == "gpt-4o-mini"
    assert isinstance(embedding, OpenAIEmbeddingModel)
    assert embedding.model_name == "text-embedding-3-small"


def test_create_rerank_is_unsupported(provider: OpenAIInferenceProvider) -> None:
    """OpenAI provider rejects rerank construction clearly."""
    with pytest.raises(ModelTypeNotSupportedError) as exc_info:
        provider._create_rerank(  # pylint: disable=protected-access
            CatalogModel(
                name="rerank",
                provider_model_id="ignored",
                model_type="rerank",
            )
        )

    assert exc_info.value.model_type == "rerank"
    assert exc_info.value.provider_id == "openai"


@pytest.mark.asyncio
async def test_get_model_instance_missing_or_wrong_type_raises(
    mocker: Any,
) -> None:
    """Typed getter raises ModelNotAvailableError for missing/wrong type."""
    mocker.patch.object(
        OpenAIInferenceProvider,
        "_build_provider",
        return_value=mocker.MagicMock(spec=OpenAIProvider),
    )
    entry = _entry(
        skip_model_discovery=True,
        allowed_models=[
            {
                "name": "chat",
                "provider_model_id": "gpt-4o-mini",
                "model_type": "llm",
            }
        ],
    )
    provider = OpenAIInferenceProvider(entry)
    await provider.initialize()

    with pytest.raises(ModelNotAvailableError) as missing:
        provider.get_model_instance("missing", "llm")
    with pytest.raises(ModelNotAvailableError) as wrong_type:
        provider.get_model_instance("chat", "embedding")

    assert missing.value.name == "missing"
    assert wrong_type.value.model_type == "embedding"
