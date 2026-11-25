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


def test_second_migration_keeps_data_and_sets_defaults(tmp_path):
    from alembic import command
    from alembic.config import Config

    from app.migrate import _ROOT

    url = f"sqlite:///{tmp_path / 'test.db'}"
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0001")

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO ingredient (ingredient_type, name, stock, change_date) "
            "VALUES ('Malz', 'Pilsner', 12.5, '2026-01-01')"
        ))
        connection.execute(text(
            "INSERT INTO ingredient_attribute (ingredient_id, attribute_name, attribute_datatype, attribute_value) "
            "VALUES (1, 'EBC', 'decimal', '3')"
        ))
    command.upgrade(config, "head")

    inspector = inspect(engine)
    ingredient_columns = {c["name"] for c in inspector.get_columns("ingredient")}
    assert "unit" in ingredient_columns
    assert "attribute_datatype" not in {c["name"] for c in inspector.get_columns("ingredient_attribute")}
    assert "alcohol_current" not in {c["name"] for c in inspector.get_columns("brewing_log")}
    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, stock, unit FROM ingredient")).one()
        attribute = connection.execute(text("SELECT attribute_name, attribute_value FROM ingredient_attribute")).one()
    assert (row.name, float(row.stock), row.unit) == ("Pilsner", 12.5, "kg")
    assert tuple(attribute) == ("EBC", "3")

    command.downgrade(config, "0001")
    assert "unit" not in {c["name"] for c in inspect(engine).get_columns("ingredient")}
