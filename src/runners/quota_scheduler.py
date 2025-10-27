"""User and cluster quota scheduler runner."""

from threading import Thread
from time import sleep
from typing import Any

import constants
from log import get_logger
from models.config import (
    Configuration,
    QuotaHandlersConfiguration,
    QuotaLimiterConfiguration,
)
from quota.connect_pg import connect_pg
from quota.connect_sqlite import connect_sqlite
from quota.sql import (
    CREATE_QUOTA_TABLE,
    INCREASE_QUOTA_STATEMENT_PG,
    INCREASE_QUOTA_STATEMENT_SQLITE,
    RESET_QUOTA_STATEMENT_PG,
    RESET_QUOTA_STATEMENT_SQLITE,
)

logger = get_logger(__name__)


def quota_scheduler(config: QuotaHandlersConfiguration) -> bool:
    """Quota scheduler task."""
    if config is None:
        logger.warning("Quota limiters are not configured, skipping")
        return False

    if config.sqlite is None and config.postgres is None:
        logger.warning("Storage for quota limiter is not set, skipping")
        return False

    if len(config.limiters) == 0:
        logger.warning("No limiters are setup, skipping")
        return False

    connection = connect(config)
    if connection is None:
        logger.warning("Can not connect to database, skipping")
        return False

    init_tables(connection)
    period = config.scheduler.period

    increase_quota_statement = get_increase_quota_statement(config)
    reset_quota_statement = get_reset_quota_statement(config)

    logger.info(
        "Quota scheduler started in separated thread with period set to %d seconds",
        period,
    )

    while True:
        logger.info("Quota scheduler sync started")
        for limiter in config.limiters:
            try:
                quota_revocation(
                    connection, limiter, increase_quota_statement, reset_quota_statement
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Quota revoke error: %s", e)
        logger.info("Quota scheduler sync finished")
        sleep(period)
    # unreachable code
    connection.close()
    return True


def get_increase_quota_statement(config: QuotaHandlersConfiguration) -> str:
    """Get the SQL statement to increase quota."""
    if config.sqlite is not None:
        return INCREASE_QUOTA_STATEMENT_SQLITE
    return INCREASE_QUOTA_STATEMENT_PG


def get_reset_quota_statement(config: QuotaHandlersConfiguration) -> str:
    """Get the SQL statement to reset quota."""
    if config.sqlite is not None:
        return RESET_QUOTA_STATEMENT_SQLITE
    return RESET_QUOTA_STATEMENT_PG


def quota_revocation(
    connection: Any,
    quota_limiter: QuotaLimiterConfiguration,
    increase_quota_statement: str,
    reset_quota_statement: str,
) -> None:
    """Quota revocation mechanism."""
    logger.info(
        "Quota revocation mechanism for limiter '%s' of type '%s'",
        quota_limiter.name,
        quota_limiter.type,
    )

    if quota_limiter.type is None:
        raise ValueError("Limiter type not set, skipping revocation")

    if quota_limiter.period is None:
        raise ValueError("Limiter period not set, skipping revocation")

    subject_id = get_subject_id(quota_limiter.type)

    if quota_limiter.quota_increase is not None:
        increase_quota(
            connection,
            increase_quota_statement,
            subject_id,
            quota_limiter.quota_increase,
            quota_limiter.period,
        )

    if quota_limiter.initial_quota is not None and quota_limiter.initial_quota > 0:
        reset_quota(
            connection,
            reset_quota_statement,
            subject_id,
            quota_limiter.initial_quota,
            quota_limiter.period,
        )


def increase_quota(
    connection: Any,
    update_statement: str,
    subject_id: str,
    increase_by: int,
    period: str,
) -> None:
    """Increase quota by specified amount."""
    logger.info(
        "Increasing quota for subject '%s' by %d when period %s is reached",
        subject_id,
        increase_by,
        period,
    )

    # for compatibility with SQLite it is not possible to use context manager
    # there
    cursor = connection.cursor()
    cursor.execute(
        update_statement,
        (
            increase_by,
            subject_id,
            period,
        ),
    )
    cursor.close()
    connection.commit()
    logger.info("Changed %d rows in database", cursor.rowcount)


def reset_quota(
    connection: Any,
    update_statement: str,
    subject_id: str,
    reset_to: int,
    period: str,
) -> None:
    """Reset quota to specified amount."""
    logger.info(
        "Resetting quota for subject '%s' to %d when period %s is reached",
        subject_id,
        reset_to,
        period,
    )

    # for compatibility with SQLite it is not possible to use context manager
    # there
    cursor = connection.cursor()
    cursor.execute(
        update_statement,
        (
            reset_to,
            subject_id,
            period,
        ),
    )
    cursor.close()
    connection.commit()
    logger.info("Changed %d rows in database", cursor.rowcount)


def get_subject_id(limiter_type: str) -> str:
    """Get subject ID based on quota limiter type."""
    match limiter_type:
        case constants.USER_QUOTA_LIMITER:
            return "u"
        case constants.CLUSTER_QUOTA_LIMITER:
            return "c"
        case _:
            return "?"


def connect(config: QuotaHandlersConfiguration) -> Any:
    """Initialize connection to database."""
    logger.info("Initializing connection to quota limiter database")
    if config.postgres is not None:
        return connect_pg(config.postgres)
    if config.sqlite is not None:
        return connect_sqlite(config.sqlite)
    return None


def init_tables(connection: Any) -> None:
    """Initialize tables used by quota limiter."""
    logger.info("Initializing tables for quota limiter")
    cursor = connection.cursor()
    cursor.execute(CREATE_QUOTA_TABLE)
    cursor.close()
    connection.commit()


def start_quota_scheduler(configuration: Configuration) -> None:
    """Start user and cluster quota scheduler in separate thread."""
    logger.info("Starting quota scheduler")
    thread = Thread(
        target=quota_scheduler,
        daemon=True,
        args=(configuration.quota_handlers,),
    )
    thread.start()
