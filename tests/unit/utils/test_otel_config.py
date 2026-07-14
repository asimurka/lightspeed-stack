"""Unit tests for OpenTelemetry environment variable collection."""

import pytest

import constants
from utils.otel_config import (
    collect_otel_environment_variables,
    is_otel_secret_env_var,
)


def test_collect_otel_environment_variables_returns_all_otel_vars() -> None:
    """All OTEL_* variables are included in sorted order."""
    environ = {
        "OTEL_SERVICE_NAME": "lightspeed-core",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
        "OTEL_PROPAGATORS": "tracecontext,baggage",
        "LIGHTSPEED_STACK_CONFIG_PATH": "/etc/config.yaml",
        "HOME": "/home/user",
    }

    result = collect_otel_environment_variables(environ)

    assert result == {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
        "OTEL_PROPAGATORS": "tracecontext,baggage",
        "OTEL_SERVICE_NAME": "lightspeed-core",
    }


def test_collect_otel_environment_variables_redacts_headers() -> None:
    """OTEL_EXPORTER_OTLP_HEADERS is redacted in the /config output."""
    environ = {
        "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer secret-token",
        "OTEL_SERVICE_NAME": "lightspeed-core",
    }

    result = collect_otel_environment_variables(environ)

    assert result["OTEL_EXPORTER_OTLP_HEADERS"] == constants.OTEL_CONFIG_REDACTED_VALUE
    assert result["OTEL_SERVICE_NAME"] == "lightspeed-core"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("OTEL_EXPORTER_OTLP_HEADERS", True),
        ("OTEL_EXPORTER_OTLP_CLIENT_KEY", True),
        ("OTEL_EXPORTER_OTLP_CLIENT_KEY_FILE", True),
        ("OTEL_AUTH_TOKEN", True),
        ("OTEL_EXPORTER_OTLP_ENDPOINT", False),
        ("OTEL_SERVICE_NAME", False),
        ("OTEL_PROPAGATORS", False),
        ("OTEL_SDK_DISABLED", False),
    ],
)
def test_is_otel_secret_env_var(name: str, expected: bool) -> None:
    """Secret detection covers headers, credentials, and non-secret settings."""
    assert is_otel_secret_env_var(name) is expected


def test_collect_otel_environment_variables_redacts_secret_patterns() -> None:
    """Variables matching secret name patterns are redacted."""
    environ = {
        "OTEL_EXPORTER_OTLP_CLIENT_KEY": "/var/run/secrets/client.key",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
    }

    result = collect_otel_environment_variables(environ)

    assert (
        result["OTEL_EXPORTER_OTLP_CLIENT_KEY"] == constants.OTEL_CONFIG_REDACTED_VALUE
    )
    assert result["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel-collector:4318"


def test_collect_otel_environment_variables_empty_when_no_otel_vars() -> None:
    """An empty mapping is returned when no OTEL_* variables are set."""
    result = collect_otel_environment_variables({"HOME": "/home/user"})

    assert not result
