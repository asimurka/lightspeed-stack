"""Llama Stack client retrieval class."""

import json
import logging
import os
import tempfile
from typing import Optional

import yaml
from llama_stack import AsyncLlamaStackAsLibraryClient  # type: ignore
from llama_stack.core.stack import replace_env_vars
from llama_stack_client import AsyncLlamaStackClient  # type: ignore

from configuration import configuration
from llama_stack_configuration import enrich_byok_rag, YamlDumper
from models.config import LlamaStackConfiguration
from utils.types import Singleton

logger = logging.getLogger(__name__)


class AsyncLlamaStackClientHolder(metaclass=Singleton):
    """Container for an initialised AsyncLlamaStackClient."""

    _lsc: Optional[AsyncLlamaStackClient] = None

    async def load(self, llama_stack_config: LlamaStackConfiguration) -> None:
        """Initialize the Llama Stack client based on configuration."""
        if llama_stack_config.use_as_library_client:
            await self._load_library_client(llama_stack_config)
        else:
            self._load_service_client(llama_stack_config)

    async def _load_library_client(self, config: LlamaStackConfiguration) -> None:
        """Initialize client in library mode."""
        if config.library_client_config_path is None:
            raise ValueError("library_client_config_path is required for library mode")

        logger.info("Initializing Llama Stack as library client")
        enriched_config_path = self._enrich_library_config(
            config.library_client_config_path
        )
        client = AsyncLlamaStackAsLibraryClient(enriched_config_path)
        await client.initialize()
        self._lsc = client

        # Set initial provider_data with Azure token if configured
        # (llama-stack needs token in provider_data at request time, not just in config)
        # if AzureEntraIDManager().is_entra_id_configured:
        #     if client.provider_data is None:
        #         client.provider_data = {}
        #     client.provider_data["azure_api_key"] = AzureEntraIDManager().access_token
        #     logger.info("Azure API key set in library client provider_data")

    def _load_service_client(self, config: LlamaStackConfiguration) -> None:
        """Initialize client in service mode (remote HTTP)."""
        logger.info("Initializing Llama Stack as remote service client")
        api_key = config.api_key.get_secret_value() if config.api_key else None
        self._lsc = AsyncLlamaStackClient(base_url=config.url, api_key=api_key)

    def _enrich_library_config(self, input_config_path: str) -> str:
        """Enrich llama-stack config with dynamic values."""
        # self._setup_azure_token()

        try:
            with open(input_config_path, "r", encoding="utf-8") as f:
                ls_config = yaml.safe_load(f)
                ls_config = replace_env_vars(ls_config)
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to read llama-stack config: %s", e)
            return input_config_path

        byok_rag = [b.model_dump() for b in configuration.configuration.byok_rag]
        enrich_byok_rag(ls_config, byok_rag)

        enriched_path = os.path.join(
            tempfile.gettempdir(), "llama_stack_enriched_config.yaml"
        )

        try:
            with open(enriched_path, "w", encoding="utf-8") as f:
                yaml.dump(ls_config, f, Dumper=YamlDumper, default_flow_style=False)
            logger.info("Wrote enriched llama-stack config to %s", enriched_path)
            return enriched_path
        except OSError as e:
            logger.warning("Failed to write enriched config: %s", e)
            return input_config_path

    # def _setup_azure_token(self) -> None:
    #     """Set up Azure Entra ID token in environment for library mode."""
    #     if not AzureEntraIDManager().is_entra_id_configured:
    #         logger.info("Azure Entra ID not configured, skipping token setup")
    #         return

    def get_client(self) -> AsyncLlamaStackClient:
        """
        Get the initialized client held by this holder.

        Returns:
            AsyncLlamaStackClient: The initialized client instance.

        Raises:
            RuntimeError: If the client has not been initialized; call `load(...)` first.
        """
        if not self._lsc:
            raise RuntimeError(
                "AsyncLlamaStackClient has not been initialised. Ensure 'load(..)' has been called."
            )
        return self._lsc

    def update_provider_data(self, updates: dict[str, str]) -> None:
        """Update provider_data with the given key-value pairs.

        For library clients: Updates provider_data attribute directly.
        For remote clients: Creates a copy with updated headers.
        """
        if not self._lsc:
            raise RuntimeError(
                "AsyncLlamaStackClient has not been initialised. Ensure 'load(..)' has been called."
            )

        if isinstance(self._lsc, AsyncLlamaStackAsLibraryClient):
            if self._lsc.provider_data is None:
                self._lsc.provider_data = {}
            self._lsc.provider_data.update(updates)
            return

        # Remote client: update via headers
        current_headers = self._lsc.default_headers or {}
        provider_data_json = current_headers.get("X-LlamaStack-Provider-Data")

        try:
            provider_data = json.loads(provider_data_json) if provider_data_json else {}
        except (json.JSONDecodeError, TypeError):
            provider_data = {}

        provider_data.update(updates)

        updated_headers = {
            **current_headers,
            "X-LlamaStack-Provider-Data": json.dumps(provider_data),
        }
        self._lsc = self._lsc.copy(set_default_headers=updated_headers)  # type: ignore
