import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import get_session
from app.main import app
from app.migrate import run_migrations


def _sqlite_factory(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(url)
    yield sessionmaker(bind=create_engine(url), expire_on_commit=False)


def _postgres_factory():
    """Isolated schema in the configured PostgreSQL database, dropped afterwards."""
    base_url = get_settings().database_url
    if not base_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    schema = f"test_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base_url)
    try:
        with admin.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {schema}"))
    except Exception as exc:
        admin.dispose()
        pytest.skip(f"PostgreSQL not available: {exc}")
    url = make_url(base_url).update_query_dict({"options": f"-csearch_path={schema}"})
    url_text = url.render_as_string(hide_password=False)
    engine = create_engine(url_text)
    try:
        run_migrations(url_text)
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def session_factory(request, tmp_path):
    """Fresh database created through the real migrations, once per dialect."""
    if request.param == "sqlite":
        yield from _sqlite_factory(tmp_path)
    else:
        yield from _postgres_factory()


@pytest.fixture
def session(session_factory) -> Session:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory):
    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    # No context manager: the lifespan would migrate the configured database.
    yield TestClient(app, follow_redirects=True, raise_server_exceptions=False)
    app.dependency_overrides.clear()
