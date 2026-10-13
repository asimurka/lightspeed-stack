"""OpenAI runtime inference provider backed by Pydantic AI."""

from __future__ import annotations

from typing import Any

from pydantic_ai.embeddings import EmbeddingModel
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from sentence_transformers import CrossEncoder

from models.config import OpenAIInferenceProviderEntry
from providers.inference.base import InferenceProvider
from providers.inference.catalog import CatalogModel, DiscoveredModel
from providers.inference.errors import ModelTypeNotSupportedError
from providers.inference.types import ModelType
from providers.inference.utils import infer_model_type


class OpenAIInferenceProvider(
    InferenceProvider[OpenAIInferenceProviderEntry, OpenAIProvider]
):
    """Inference provider for OpenAI and OpenAI-compatible HTTP APIs."""

    def _build_provider(self) -> OpenAIProvider:
        """Build PAI's OpenAI provider from the configured API key and URL."""
        config = self._entry.config
        api_key = (
            config.api_key.get_secret_value() if config.api_key is not None else None
        )
        return OpenAIProvider(api_key=api_key, base_url=config.base_url)

    async def _discover_models(self) -> list[DiscoveredModel]:
        """List models from the OpenAI-compatible ``/models`` endpoint."""
        response = await self._get_provider.client.models.list()
        return [
            DiscoveredModel(
                provider_model_id=model.id,
                model_type=self._infer_model_type(model.id),
            )
            for model in response.data
        ]

    def _create_llm(self, model: CatalogModel) -> Model:
        """Construct a Responses API chat model for the catalog entry."""
        return OpenAIResponsesModel(
            model.provider_model_id,
            provider=self._get_provider,
        )

    def _create_embedding(self, model: CatalogModel) -> EmbeddingModel:
        """Construct an OpenAI embedding model for the catalog entry."""
        return OpenAIEmbeddingModel(
            model.provider_model_id,
            provider=self._get_provider,
        )

    def _create_rerank(self, model: CatalogModel) -> CrossEncoder:
        """Raise when rerank is requested; this provider has no rerank API."""
        _ = model
        raise ModelTypeNotSupportedError("rerank", self.provider_id)

    def _infer_model_type(
        self,
        provider_model_id: str,
        **kwargs: Any,
    ) -> ModelType:
        """Classify a wire model id using PAI known LLM and embedding names.

        Args:
            provider_model_id: Model identifier from OpenAI or an allow-list.
            **kwargs: Unused; accepted for ABC compatibility.

        Returns:
            Inferred catalog model type.

        """
        _ = kwargs
        return infer_model_type(provider_model_id)
