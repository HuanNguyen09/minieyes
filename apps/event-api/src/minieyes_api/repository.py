"""Event storage. One SQLAlchemy implementation serves SQLite (unit tests) and Postgres."""

from datetime import datetime

from sqlalchemy import Engine, insert, select
from sqlalchemy.exc import IntegrityError

from minieyes_api.db import events
from minieyes_api.schemas import EventIn, EventOut


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
