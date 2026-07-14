"""Collect OpenTelemetry environment variables for the /config endpoint."""

import os
import re
from collections.abc import Mapping
from typing import Final

import constants

_OTEL_SECRET_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(SECRET|TOKEN|PASSWORD|CREDENTIAL|HEADERS|CLIENT_KEY)",
    re.IGNORECASE,
)

_OTEL_EXPLICIT_SECRET_VARS: Final[frozenset[str]] = frozenset(
    {"OTEL_EXPORTER_OTLP_HEADERS"}
)


def is_otel_secret_env_var(name: str) -> bool:
    """Return whether an OTEL_* environment variable value should be redacted.

    Parameters:
        name: Environment variable name (expected to start with ``OTEL_``).

    Returns:
        True when the variable is known to carry secrets.
    """
    if name in _OTEL_EXPLICIT_SECRET_VARS:
        return True
    return _OTEL_SECRET_NAME_PATTERN.search(name) is not None


def collect_otel_environment_variables(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Collect OTEL_* environment variables with secrets redacted.

    Parameters:
        environ: Environment mapping to read from. Defaults to ``os.environ``.

    Returns:
        OTEL_* variable names mapped to values, sorted alphabetically by name.
    """
    source = os.environ if environ is None else environ
    result: dict[str, str] = {}
    for name, value in source.items():
        if not name.startswith(constants.OTEL_ENV_VAR_PREFIX):
            continue
        if is_otel_secret_env_var(name):
            result[name] = constants.OTEL_CONFIG_REDACTED_VALUE
        else:
            result[name] = value
    return dict(sorted(result.items()))
