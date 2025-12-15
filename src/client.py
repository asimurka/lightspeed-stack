"""Llama Stack client retrieval class."""

import json
import logging
import os
import tempfile
from typing import Optional

from llama_stack import (
    AsyncLlamaStackAsLibraryClient,  # type: ignore
)
from llama_stack_client import AsyncLlamaStackClient  # type: ignore
from configuration import configuration
from llama_stack_configuration import generate_configuration
from models.config import LlamaStackConfiguration
from utils.types import Singleton


logger = logging.getLogger(__name__)


class AsyncLlamaStackClientHolder(metaclass=Singleton):
    """Container for an initialised AsyncLlamaStackClient."""

    _lsc: Optional[AsyncLlamaStackClient] = None

    async def load(self, llama_stack_config: LlamaStackConfiguration) -> None:
        """
        Load and initialize the holder's AsyncLlamaStackClient according to the provided config.

        If `llama_stack_config.use_as_library_client` is set to True, a
        library-mode client is created using
        `llama_stack_config.library_client_config_path` and initialized before
        being stored.

        Otherwise, a service-mode client is created using
        `llama_stack_config.url` and optional `llama_stack_config.api_key`.
        The created client is stored on the instance for later retrieval via
        `get_client()`.

        Parameters:
            llama_stack_config (LlamaStackConfiguration): Configuration that
            selects client mode and provides either a library client config
            path or service connection details (URL and optional API key).

        Raises:
            ValueError: If `use_as_library_client` is True but
            `library_client_config_path` is not set.
        """
        if llama_stack_config.use_as_library_client is True:
            if llama_stack_config.library_client_config_path is not None:
                logger.info("Using Llama stack as library client")

                # Enrich the llama-stack config with dynamic values before loading
                enriched_config_path = self._enrich_library_config(
                    llama_stack_config.library_client_config_path
                )

                client = AsyncLlamaStackAsLibraryClient(enriched_config_path)
                await client.initialize()
                self._lsc = client
            else:
                msg = "Configuration problem: library_client_config_path option is not set"
                logger.error(msg)
                # tisnik: use custom exception there - with cause etc.
                raise ValueError(msg)
        else:
            logger.info("Using Llama stack running as a service")
            self._lsc = AsyncLlamaStackClient(
                base_url=llama_stack_config.url,
                api_key=(
                    llama_stack_config.api_key.get_secret_value()
                    if llama_stack_config.api_key is not None
                    else None
                ),
            )

    def _enrich_library_config(self, input_config_path: str) -> str:
        """Enrich llama-stack config with dynamic values from lightspeed config.

        Returns the path to the enriched config file.
        """
        # Generate enriched config to a temp file
        # Use a deterministic name so we don't create multiple temp files
        enriched_path = os.path.join(
            tempfile.gettempdir(), "llama_stack_enriched_config.yaml"
        )

        try:
            generate_configuration(
                input_config_path,
                enriched_path,
                configuration.configuration,
            )
            logger.info(
                "Enriched llama-stack config: %s -> %s",
                input_config_path,
                enriched_path,
            )
            return enriched_path
        except Exception as e:
            logger.warning(
                "Failed to enrich llama-stack config, using original: %s", e
            )
            return input_config_path

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

    def set_client(self, new_client: AsyncLlamaStackClient) -> None:
        """
        Replace the currently stored AsyncLlamaStackClient instance.

        This method allows updating the client reference when
        configuration or runtime attributes have changed.
        """
        self._lsc = new_client

    def update_provider_data(self, updates: dict[str, str]) -> AsyncLlamaStackClient:
        """Update provider_data with the given key-value pairs, preserving existing data.

        For library clients (AsyncLlamaStackAsLibraryClient): Updates the provider_data
        attribute directly since library clients don't support the copy() method.
        For remote clients (AsyncLlamaStackClient): Creates a copy with updated headers.
        """
        if not self._lsc:
            raise RuntimeError(
                "AsyncLlamaStackClient has not been initialised. Ensure 'load(..)' has been called."
            )

        # Library client: update provider_data directly
        if isinstance(self._lsc, AsyncLlamaStackAsLibraryClient):
            if self._lsc.provider_data is None:
                self._lsc.provider_data = {}
            self._lsc.provider_data.update(updates)
            return self._lsc

        # Remote client: create a copy with updated headers
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
        return self._lsc.copy(set_default_headers=updated_headers)  # type: ignore
