from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from minieyes_api.db import metadata
from minieyes_api.migrate import upgrade


def test_upgrade_creates_events_with_a_unique_event_id_index(tmp_path):
    url = f"sqlite:///{tmp_path / 'api.db'}"

    upgrade(url)

    tables = inspect(create_engine(url))
    assert "events" in tables.get_table_names()
    unique = [ix for ix in tables.get_indexes("events") if ix["unique"]]
    assert [ix["column_names"] for ix in unique] == [["event_id"]]


def test_the_migrated_schema_matches_the_application_metadata(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    upgrade(str(engine.url))

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), metadata)

    assert diff == []


def test_upgrade_twice_is_a_no_op(tmp_path):
    url = f"sqlite:///{tmp_path / 'api.db'}"

    upgrade(url)
    upgrade(url)
