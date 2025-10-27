"""Unit tests for Customization model."""

import pytest
from pydantic import ValidationError
from pytest_subtests import SubTests

from models.config import Customization


def test_service_customization(subtests: SubTests) -> None:
    """Check the service customization class."""
    with subtests.test(msg="System prompt is enabled"):
        c = Customization()
        assert c is not None
        assert c.disable_query_system_prompt is False
        assert c.system_prompt_path is None
        assert c.system_prompt is None

    with subtests.test(msg="System prompt is disabled"):
        c = Customization(disable_query_system_prompt=True)
        assert c is not None
        assert c.disable_query_system_prompt is True
        assert c.system_prompt_path is None
        assert c.system_prompt is None

    with subtests.test(
        msg="Disabled overrides provided path, but the prompt is still loaded"
    ):
        c = Customization(
            disable_query_system_prompt=True,
            system_prompt_path="tests/configuration/system_prompt.txt",
        )
        assert c.system_prompt is not None
        # check that the system prompt has been loaded from the provided file
        assert c.system_prompt == "This is system prompt."
        # but it is still disabled
        assert c.disable_query_system_prompt is True


def test_service_customization_wrong_system_prompt_path() -> None:
    """Check the service customization class."""
    with pytest.raises(ValidationError, match="Path does not point to a file"):
        _ = Customization(system_prompt_path="/path/does/not/exists")


def test_service_customization_correct_system_prompt_path(subtests: SubTests) -> None:
    """Check the service customization class."""
    with subtests.test(msg="One line system prompt"):
        # pass a file containing system prompt
        c = Customization(system_prompt_path="tests/configuration/system_prompt.txt")
        assert c is not None
        # check that the system prompt has been loaded from the provided file
        assert c.system_prompt == "This is system prompt."

    with subtests.test(msg="Multi line system prompt"):
        # pass a file containing system prompt
        c = Customization(
            system_prompt_path="tests/configuration/multiline_system_prompt.txt"
        )
        assert c is not None
        # check that the system prompt has been loaded from the provided file
        assert "You are OpenShift Lightspeed" in c.system_prompt
        assert "Here are your instructions" in c.system_prompt
        assert "Here are some basic facts about OpenShift" in c.system_prompt
