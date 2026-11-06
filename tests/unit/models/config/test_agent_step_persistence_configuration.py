"""Tests for agent step persistence (discriminated union)."""

import pytest
from pydantic import TypeAdapter, ValidationError

from models.config import (
    AgentStepPersistenceFileConfiguration,
    AgentStepPersistenceRoot,
    AgentStepPersistenceSqliteConfiguration,
    SQLiteDatabaseConfiguration,
)


@pytest.fixture(name="adapter")
def adapter_fixture() -> TypeAdapter[AgentStepPersistenceRoot]:
    """Type adapter for the union."""
    return TypeAdapter(AgentStepPersistenceRoot)


def test_default_explicit(adapter: TypeAdapter[AgentStepPersistenceRoot]) -> None:
    """Explicit ``type: default`` parses."""
    cfg = adapter.validate_python({"type": "default"})
    assert cfg.type == "default"


def test_file_variant(adapter: TypeAdapter[AgentStepPersistenceRoot]) -> None:
    """``type: file`` requires a directory."""
    cfg = adapter.validate_python(
        {"type": "file", "file_directory": "/data/agent_steps"}
    )
    assert isinstance(cfg, AgentStepPersistenceFileConfiguration)
    assert cfg.file_directory == "/data/agent_steps"


def test_sqlite_variant(adapter: TypeAdapter[AgentStepPersistenceRoot]) -> None:
    """``type: sqlite`` nests SQLite configuration."""
    cfg = adapter.validate_python(
        {
            "type": "sqlite",
            "sqlite": SQLiteDatabaseConfiguration(db_path="/tmp/steps.db"),
        }
    )
    assert isinstance(cfg, AgentStepPersistenceSqliteConfiguration)
    assert cfg.sqlite.db_path == "/tmp/steps.db"


def test_legacy_file_directory_only(
    adapter: TypeAdapter[AgentStepPersistenceRoot],
) -> None:
    """Legacy YAML with only ``file_directory`` coerces to ``type: file``."""
    cfg = adapter.validate_python({"file_directory": "/legacy/dir"})
    assert cfg.type == "file"
    assert cfg.file_directory == "/legacy/dir"


def test_legacy_sqlite_only(adapter: TypeAdapter[AgentStepPersistenceRoot]) -> None:
    """Legacy YAML with only ``sqlite`` coerces to ``type: sqlite``."""
    cfg = adapter.validate_python(
        {"sqlite": SQLiteDatabaseConfiguration(db_path="/legacy/db.sqlite")}
    )
    assert cfg.type == "sqlite"
    assert cfg.sqlite.db_path == "/legacy/db.sqlite"


def test_legacy_both_backends_rejected(
    adapter: TypeAdapter[AgentStepPersistenceRoot],
) -> None:
    """Legacy shape rejects both ``file_directory`` and ``sqlite``."""
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "file_directory": "/a",
                "sqlite": SQLiteDatabaseConfiguration(db_path="/b.db"),
            }
        )
