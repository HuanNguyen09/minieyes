"""Event storage. One SQLAlchemy implementation serves SQLite (unit tests) and Postgres."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, and_, insert, or_, select
from sqlalchemy.exc import IntegrityError

from minieyes_api.cursor import Position
from minieyes_api.db import events
from minieyes_api.schemas import EventIn, EventOut


@dataclass(frozen=True)
class EventFilter:
    """Conditions for listing events; None means "any"."""

    site: str
    camera: str | None = None
    zone: str | None = None
    since: datetime | None = None  # inclusive
    until: datetime | None = None  # exclusive


class EventRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def add(self, event: EventIn, received_at: datetime) -> tuple[EventOut, bool]:
        """Store the event unless its event_id exists; return the stored event and whether it
        was created now. The unique index decides, so concurrent duplicates are safe."""
        x1, y1, x2, y2 = event.bbox
        row = {
            **event.model_dump(exclude={"bbox"}),
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "received_at": received_at,
        }
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(events).values(row))
            created = True
        except IntegrityError:
            created = False
        stored = self.get(event.event_id)
        assert stored is not None
        return stored, created

    def get(self, event_id) -> EventOut | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(events).where(events.c.event_id == event_id)).first()
        return None if row is None else _to_event(row)

    def page(
        self, filters: EventFilter, limit: int, after: Position | None = None
    ) -> tuple[list[EventOut], Position | None]:
        """Up to `limit` events newest first, starting after `after`, and the position to
        continue from (None on the last page). Ties on occurred_at are broken by row id, so
        pages neither skip nor repeat events, even while newer ones arrive."""
        t, row_id = events.c.occurred_at, events.c.id
        query = select(events).order_by(t.desc(), row_id.desc()).limit(limit + 1)
        for column in ("site", "camera", "zone"):
            value = getattr(filters, column)
            if value is not None:
                query = query.where(events.c[column] == value)
        if filters.since is not None:
            query = query.where(t >= filters.since)
        if filters.until is not None:
            query = query.where(t < filters.until)
        if after is not None:
            query = query.where(
                or_(t < after.occurred_at, and_(t == after.occurred_at, row_id < after.id))
            )
        with self._engine.connect() as conn:
            rows = conn.execute(query).all()
        if len(rows) <= limit:
            return [_to_event(row) for row in rows], None
        rows = rows[:limit]
        last = rows[-1]._mapping
        return [_to_event(row) for row in rows], Position(last["occurred_at"], last["id"])


def _to_event(row) -> EventOut:
    m = row._mapping
    return EventOut(
        event_id=m["event_id"],
        site=m["site"],
        camera=m["camera"],
        zone=m["zone"],
        type=m["type"],
        confidence=m["confidence"],
        bbox=(m["x1"], m["y1"], m["x2"], m["y2"]),
        occurred_at=m["occurred_at"],
        received_at=m["received_at"],
    )
