"""Unsorted utility functions to be used from other sources and test step definitions."""

import os
import shutil
import subprocess
import time
from typing import Any
import json
import jsonschema


def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint to be added into the URL."""
    endpoint = endpoint.replace('"', "")
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return endpoint


def validate_json(message: Any, schema: Any) -> None:
    """Check the JSON message with the given schema."""
    try:
        jsonschema.validate(
            instance=message,
            schema=schema,
        )

    except jsonschema.ValidationError as e:
        assert False, "The message doesn't fit the expected schema:" + str(e)

    except jsonschema.SchemaError as e:
        assert False, "The provided schema is faulty:" + str(e)


def wait_for_container_health(container_name: str, max_attempts: int = 3) -> None:
    """Wait for container to be healthy."""
    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format={{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            if result.stdout.strip() == "healthy":
                break
            else:
                if attempt < max_attempts - 1:
                    time.sleep(5)
                else:
                    print(
                        f"{container_name} not healthy after {max_attempts * 5} seconds"
                    )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        if attempt < max_attempts - 1:
            print(f"⏱ Attempt {attempt + 1}/{max_attempts} - waiting...")
            time.sleep(5)
        else:
            print(f"Could not check health status for {container_name}")


def switch_config_and_restart(
    original_file: str,
    replacement_file: str,
    container_name: str,
    cleanup: bool = False,
) -> str:
    """Switch configuration file and restart container.

    Args:
        original_file: Path to the original configuration file
        replacement_file: Path to the replacement configuration file
        container_name: Name of the container to restart
        cleanup: If True, remove the backup file after restoration (default: False)

    Returns:
        str: Path to the backup file for restoration
    """
    backup_file = f"{original_file}.backup"

    if not cleanup and not os.path.exists(backup_file):
        try:
            shutil.copy(original_file, backup_file)
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"Failed to create backup: {e}")
            raise

    try:
        shutil.copy(replacement_file, original_file)
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"Failed to copy replacement file: {e}")
        raise

    # Restart container
    try:
        subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"Failed to restart container {container_name}: {e.stderr}")
        raise

    # Wait for container to be healthy
    wait_for_container_health(container_name)

    # Clean up backup file
    if cleanup and os.path.exists(backup_file):
        try:
            os.remove(backup_file)
        except OSError as e:
            print(f"Warning: Could not remove backup file {backup_file}: {e}")

    return backup_file


def _check_json(actual: Any, expected: Any, path: str):
    if isinstance(expected, dict):
        for key, value in expected.items():
            assert key in actual, f"Missing key {path + key}"
            _check_json(value, actual[key], path + key + ".")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"Expected list at {path}"
        assert len(actual) >= len(expected), f"List too short at {path}"
        for i, j in sorted(expected), sorted(actual):
            _check_json(i, j, path + f"[{i}].")
    else:
        assert expected == actual, f"Mismatch at {path[:-1]}: expected {expected}, got {actual}"


def validate_json_partially(actual: dict, expected: dict) -> None:
    """Validate all keys and values in expected JSON string exist in actual dict; extra keys are ignored."""
    _check_json(actual, expected, "")

