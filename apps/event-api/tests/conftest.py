import hashlib

import pytest
from fakes import FakeNow
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.pool import StaticPool

from minieyes_api.app import create_app
from minieyes_api.db import events, metadata
from minieyes_api.migrate import upgrade
from minieyes_api.settings import Settings

KEY_SITE_01 = "key-for-site-01"
KEY_SITE_02 = "key-for-site-02"


def sha256(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def valid_event(**overrides) -> dict:
    event = {
        "event_id": "00000000-0000-4000-8000-000000000001",
        "site": "site-01",
        "camera": "cam1",
        "zone": "forklift-lane",
        "type": "red_zone_intrusion",
        "confidence": 0.82,
        "bbox": [12.0, 40.5, 88.0, 230.0],
        "occurred_at": "2026-11-03T08:15:02Z",
    }
    event.update(overrides)
    return event


def count_rows(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(events)).scalar_one()


@pytest.fixture(scope="session")
def postgres_url():
    """A throwaway Postgres 16, migrated with Alembic exactly like production."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        url = pg.get_connection_url()
        upgrade(url)
        yield url


# Every test that uses `engine` runs on SQLite; with `-m integration` it also runs on Postgres,
# so both backends are held to the same contract.
@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.integration)])
def engine(request):
    if request.param == "sqlite":
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        metadata.create_all(engine)
    else:
        engine = create_engine(request.getfixturevalue("postgres_url"))
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE events RESTART IDENTITY"))
    yield engine
    engine.dispose()


@pytest.fixture
def settings():
    return Settings(
        api_keys={"site-01": sha256(KEY_SITE_01), "site-02": sha256(KEY_SITE_02)},
        database_url="sqlite://",
    )


@pytest.fixture
def registry():
    return CollectorRegistry()


@pytest.fixture
def now():
    return FakeNow()


@pytest.fixture
def client(settings, engine, registry, now):
    app = create_app(settings, engine, registry=registry, now=now)
    with TestClient(app) as client:
        yield client
