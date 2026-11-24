"""Runs pending Alembic migrations at application start."""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent


class MigrationError(RuntimeError):
    """Raised when the database cannot be brought to the current schema version."""


def run_migrations(database_url: str | None = None) -> None:
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "migrations"))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        logger.exception("Database migration failed")
        raise MigrationError(
            f"Database migration failed, application will not start: {exc}"
        ) from exc
    logger.info("Database schema is up to date")
