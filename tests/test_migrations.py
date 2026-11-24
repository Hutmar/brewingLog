import pytest
from sqlalchemy import create_engine, inspect, text

from app.migrate import MigrationError, run_migrations

EXPECTED = {"recipe", "ingredient", "ingredient_attribute", "brewing_log", "rating"}


def test_migration_creates_schema_and_is_repeatable(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(url)
    run_migrations(url)
    tables = set(inspect(create_engine(url)).get_table_names())
    assert EXPECTED <= tables


def test_migration_keeps_existing_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(url)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO recipe (recipe_name) VALUES ('Keep me')"))
    run_migrations(url)
    with engine.connect() as connection:
        names = connection.execute(text("SELECT recipe_name FROM recipe")).scalars().all()
    assert names == ["Keep me"]


def test_failing_migration_raises_readable_error(tmp_path, caplog):
    unreachable = f"sqlite:///{tmp_path / 'missing-dir' / 'test.db'}"
    with pytest.raises(MigrationError, match="Database migration failed"):
        run_migrations(unreachable)
    assert "Database migration failed" in caplog.text
