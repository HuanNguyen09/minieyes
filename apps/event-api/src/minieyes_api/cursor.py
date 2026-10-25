"""Opaque pagination cursors: a position in (occurred_at desc, id desc) order."""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Position:
    """The last event of a page; the next page starts strictly after it."""

    occurred_at: datetime
    id: int


class InvalidCursor(ValueError):
    pass


def encode(position: Position) -> str:
    raw = json.dumps([position.occurred_at.isoformat(), position.id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(cursor: str) -> Position:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        occurred_at, row_id = json.loads(raw)
        position = Position(datetime.fromisoformat(occurred_at), int(row_id))
    except (binascii.Error, ValueError, TypeError) as exc:
        raise InvalidCursor(cursor) from exc
    if position.occurred_at.tzinfo is None:
        raise InvalidCursor(cursor)
    return position
