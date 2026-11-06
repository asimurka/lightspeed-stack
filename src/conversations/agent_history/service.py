"""Configure and share the agent step store for the process."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_ai_harness.step_persistence import (
    SqliteStepStore,
    StepPersistence,
    StepStore,
)

from log import get_logger
from models.config import (
    AgentStepPersistenceConfiguration,
    AgentStepPersistenceNoopConfiguration,
    AgentStepPersistenceSqliteConfiguration,
)
from utils.types import Singleton

logger = get_logger(__name__)


class AgentHistoryService(metaclass=Singleton):
    """Singleton holder for the agent step store."""

    def __init__(self) -> None:
        """Create an uninitialized service.

        Call initialize after configuration is loaded.
        """
        self._store: Optional[StepStore] = None

    def initialize(self, config: AgentStepPersistenceConfiguration) -> None:
        """Open the step store from service configuration.

        Args:
            config: Persistence settings for agent steps.

        """
        match config:
            case AgentStepPersistenceNoopConfiguration():
                self._store = None
            case AgentStepPersistenceSqliteConfiguration() as sqlite:
                logger.info(
                    "Creating SQLite agent step store at %s", sqlite.sqlite.db_path
                )
                self._store = SqliteStepStore(database=Path(sqlite.sqlite.db_path))

    def clear_store(self) -> None:
        """Clear the active store without opening a new one."""
        self._store = None

    @property
    def store(self) -> Optional[StepStore]:
        """Return the configured step store, or None when persistence is off."""
        return self._store

    @property
    def step_persistence(self) -> Optional[StepPersistence[object]]:
        """Return the agent persistence capability, or None when persistence is off."""
        if self._store is None:
            return None
        return StepPersistence(store=self._store)
