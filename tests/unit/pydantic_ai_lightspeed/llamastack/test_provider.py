"""Unit tests for pydantic_ai_lightspeed.llamastack._provider module."""

# pylint: disable=protected-access

import httpx
from ogx.core.library_client import AsyncOGXAsLibraryClient, OGXAsLibraryClient
from ogx_client import OgxClient
from openai import AsyncOpenAI
from pytest_mock import MockerFixture

from pydantic_ai_lightspeed.llamastack._provider import (
    DEFAULT_BASE_URL,
    OgxProvider,
)
from pydantic_ai_lightspeed.llamastack._transport import OgxServerTransport


class TestOgxProviderProperties:
    """Tests for OgxProvider basic properties."""

    def test_name(self) -> None:
        """Test that the provider name is 'llama-stack'."""
        provider = OgxProvider()
        assert provider.name == "llama-stack"

    def test_base_url_default(self) -> None:
        """Test that the default base URL matches the expected default."""
        provider = OgxProvider()
        assert DEFAULT_BASE_URL in provider.base_url

    def test_client_returns_async_openai(self) -> None:
        """Test that the client property returns an AsyncOpenAI instance."""
        provider = OgxProvider()
        assert isinstance(provider.client, AsyncOpenAI)

    def test_repr(self) -> None:
        """Test the string representation of the provider."""
        provider = OgxProvider()
        result = repr(provider)
        assert "OgxProvider" in result
        assert "llama-stack" in result

    def test_model_profile_known_model(self) -> None:
        """Test model_profile returns a profile for a known OpenAI model."""
        profile = OgxProvider.model_profile("gpt-4o")
        assert profile is not None

    def test_model_profile_unknown_model(self) -> None:
        """Test model_profile returns a default profile for an unrecognized model."""
        profile = OgxProvider.model_profile("totally-unknown-model-xyz")
        assert profile is not None


class TestOgxProviderServerMode:
    """Tests for OgxProvider server mode initialization."""

    def test_explicit_base_url(self) -> None:
        """Test that an explicit base_url is used."""
        provider = OgxProvider(base_url="http://my-server:9999/v1")
        assert "my-server:9999" in provider.base_url

    def test_explicit_api_key(self) -> None:
        """Test that an explicit api_key is used."""
        provider = OgxProvider(api_key="my-secret-key")
        assert provider.client.api_key == "my-secret-key"

    def test_default_api_key_is_not_needed(self) -> None:
        """Test that the default API key is 'not-needed'."""
        provider = OgxProvider()
        assert provider.client.api_key == "not-needed"

    def test_custom_http_client(self, mocker: MockerFixture) -> None:
        """Test that a provided http_client is wired into the provider."""
        custom_client = mocker.Mock(spec=httpx.AsyncClient)
        provider = OgxProvider(http_client=custom_client)
        assert provider._client._client is custom_client


class TestOgxProviderLibraryMode:
    """Tests for OgxProvider library mode initialization."""

    def test_library_client_creates_transport(self, mocker: MockerFixture) -> None:
        """Test that providing a library_client sets up the transport-based client."""
        mock_lib_client = mocker.Mock()
        mock_lib_client.provider_data = None

        provider = OgxProvider(library_client=mock_lib_client)

        assert provider._library_client is mock_lib_client
        assert "llama-stack-library" in provider.base_url

    def test_library_client_api_key_is_not_needed(self, mocker: MockerFixture) -> None:
        """Test that library mode sets the API key to 'not-needed'."""
        mock_lib_client = mocker.Mock()
        mock_lib_client.provider_data = None

        provider = OgxProvider(library_client=mock_lib_client)

        assert provider.client.api_key == "not-needed"


class TestFromOgxClient:
    """Tests for OgxProvider.from_ogx_client."""

    def test_library_client_dispatches_to_library_mode(
        self, mocker: MockerFixture
    ) -> None:
        """Test that an OGXAsLibraryClient creates a library-mode provider."""
        mock_async = mocker.Mock(spec=AsyncOGXAsLibraryClient)
        mock_async.provider_data = None
        mock_lib_client = mocker.Mock(spec=OGXAsLibraryClient)
        mock_lib_client.async_client = mock_async

        provider = OgxProvider.from_ogx_client(mock_lib_client)

        assert provider._library_client is mock_async
        assert "llama-stack-library" in provider.base_url

    def _mock_ogx_client(
        self,
        mocker: MockerFixture,
        *,
        base_url: str,
        api_key: str | None = "test-key",
        headers: dict[str, str] | None = None,
    ):
        """Build a mock sync OgxClient with api_client.default_headers."""
        mock_client = mocker.Mock(spec=OgxClient)
        mock_client.base_url = base_url
        mock_client.api_key = api_key
        mock_client.api_client = mocker.Mock()
        mock_client.api_client.default_headers = headers or {}
        return mock_client

    def test_server_client_extracts_base_url_with_v1(
        self, mocker: MockerFixture
    ) -> None:
        """Test that a server client whose base_url already ends with /v1 is used as-is."""
        mock_client = self._mock_ogx_client(
            mocker, base_url="http://my-server:8321/v1"
        )

        provider = OgxProvider.from_ogx_client(mock_client)

        assert "my-server:8321/v1" in provider.base_url
        assert provider.base_url.count("/v1") == 1

    def test_server_client_appends_v1_when_missing(self, mocker: MockerFixture) -> None:
        """Test that /v1 is appended when the server client's base_url lacks it."""
        mock_client = self._mock_ogx_client(mocker, base_url="http://my-server:8321")

        provider = OgxProvider.from_ogx_client(mock_client)

        assert provider.base_url.rstrip("/").endswith("/v1")

    def test_server_client_strips_trailing_slash_before_appending_v1(
        self, mocker: MockerFixture
    ) -> None:
        """Test that a trailing slash is stripped before appending /v1."""
        mock_client = self._mock_ogx_client(mocker, base_url="http://my-server:8321/")

        provider = OgxProvider.from_ogx_client(mock_client)

        assert "//v1" not in provider.base_url
        assert provider.base_url.rstrip("/").endswith("/v1")

    def test_server_client_uses_provided_api_key(self, mocker: MockerFixture) -> None:
        """Test that the server client's api_key is forwarded to the provider."""
        mock_client = self._mock_ogx_client(
            mocker, base_url="http://my-server:8321/v1", api_key="my-secret"
        )

        provider = OgxProvider.from_ogx_client(mock_client)

        assert provider.client.api_key == "my-secret"

    def test_server_client_defaults_api_key_when_none(
        self, mocker: MockerFixture
    ) -> None:
        """Test that a None api_key falls back to 'not-needed'."""
        mock_client = self._mock_ogx_client(
            mocker, base_url="http://my-server:8321/v1", api_key=None
        )

        provider = OgxProvider.from_ogx_client(mock_client)

        assert provider.client.api_key == "not-needed"

    def test_server_client_uses_fresh_async_http_client(
        self, mocker: MockerFixture
    ) -> None:
        """Test that server mode builds a fresh async httpx client."""
        mock_client = self._mock_ogx_client(
            mocker, base_url="http://my-server:8321/v1"
        )
        fresh = mocker.Mock(spec=httpx.AsyncClient)
        mocker.patch(
            "pydantic_ai_lightspeed.llamastack._provider.create_async_http_client",
            return_value=fresh,
        )

        provider = OgxProvider.from_ogx_client(mock_client)

        assert provider._client._client is fresh

    def test_server_client_wraps_transport_with_provider_data(
        self, mocker: MockerFixture
    ) -> None:
        """Test provider data from default_headers is forwarded in server mode."""
        mock_client = self._mock_ogx_client(
            mocker,
            base_url="http://my-server:8321/v1",
            headers={"X-OGX-Provider-Data": '{"azure_api_key": "token"}'},
        )

        provider = OgxProvider.from_ogx_client(mock_client)

        assert isinstance(
            provider._client._client._transport,  # pylint: disable=protected-access
            OgxServerTransport,
        )


class TestSetHttpClient:  # pylint: disable=too-few-public-methods
    """Tests for OgxProvider._set_http_client."""

    def test_replaces_internal_http_client(self, mocker: MockerFixture) -> None:
        """Test that _set_http_client replaces the underlying httpx client."""
        provider = OgxProvider()
        new_client = mocker.Mock(spec=httpx.AsyncClient)

        provider._set_http_client(new_client)

        assert provider._client._client is new_client
