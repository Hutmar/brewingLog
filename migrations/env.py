"""Alembic environment; the database URL comes from the application settings."""
from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.models import Base

target_metadata = Base.metadata


def _url() -> str:
    # An explicit URL on the Alembic config (e.g. from tests) takes precedence.
    return context.config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
