"""Database schema. Alembic migrations must keep the database in step with this table."""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Dialect,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    TypeDecorator,
    Uuid,
)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores aware datetimes as UTC and always reads them back aware.

    Postgres keeps the zone in timestamptz; SQLite drops it, so values are normalised to UTC on
    the way in (which also keeps SQLite's string comparisons correct) and tagged UTC on the way
    out.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; pass an aware datetime")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", Uuid, nullable=False),
    Column("site", String(64), nullable=False),
    Column("camera", String(64), nullable=False),
    Column("zone", String(64), nullable=False),
    Column("type", String(64), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("x1", Float, nullable=False),
    Column("y1", Float, nullable=False),
    Column("x2", Float, nullable=False),
    Column("y2", Float, nullable=False),
    Column("occurred_at", UTCDateTime, nullable=False),
    Column("received_at", UTCDateTime, nullable=False),
    Index("ux_events_event_id", "event_id", unique=True),
)
