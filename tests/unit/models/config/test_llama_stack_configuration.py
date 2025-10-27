"""Unit tests for LlamaStackConfiguration model."""

import pytest

from models.config import LlamaStackConfiguration
from utils.checks import InvalidConfigurationError


def test_llama_stack_configuration_constructor() -> None:
    """
    Verify that the LlamaStackConfiguration constructor accepts
    valid combinations of parameters and creates instances
    successfully.
    """
    llama_stack_configuration = LlamaStackConfiguration(
        use_as_library_client=True,
        library_client_config_path="tests/configuration/run.yaml",
    )
    assert llama_stack_configuration is not None

    llama_stack_configuration = LlamaStackConfiguration(
        use_as_library_client=False, url="http://localhost"
    )
    assert llama_stack_configuration is not None

    llama_stack_configuration = LlamaStackConfiguration(url="http://localhost")
    assert llama_stack_configuration is not None

    llama_stack_configuration = LlamaStackConfiguration(
        use_as_library_client=False, url="http://localhost", api_key="foo"
    )
    assert llama_stack_configuration is not None


def test_llama_stack_configuration_no_run_yaml() -> None:
    """
    Verify that constructing a LlamaStackConfiguration with a
    non-existent or invalid library_client_config_path raises
    InvalidConfigurationError.
    """
    with pytest.raises(
        InvalidConfigurationError,
        match="Llama Stack configuration file 'not a file' is not a file",
    ):
        LlamaStackConfiguration(
            use_as_library_client=True,
            library_client_config_path="not a file",
        )


def test_llama_stack_wrong_configuration_constructor_no_url() -> None:
    """
    Verify that constructing a LlamaStackConfiguration without
    specifying either a URL or enabling library client mode raises
    a ValueError.
    """
    with pytest.raises(
        ValueError,
        match="Llama stack URL is not specified and library client mode is not specified",
    ):
        LlamaStackConfiguration()


def test_llama_stack_wrong_configuration_constructor_library_mode_off() -> None:
    """Test the LlamaStackConfiguration constructor."""
    with pytest.raises(
        ValueError,
        match="Llama stack URL is not specified and library client mode is not enabled",
    ):
        LlamaStackConfiguration(use_as_library_client=False)


def test_llama_stack_wrong_configuration_no_config_file() -> None:
    """Test the LlamaStackConfiguration constructor."""
    m = "Llama stack library client mode is enabled but a configuration file path is not specified"
    with pytest.raises(ValueError, match=m):
        LlamaStackConfiguration(use_as_library_client=True)
