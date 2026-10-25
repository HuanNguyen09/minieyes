import base64
from datetime import UTC, datetime

import pytest

from minieyes_api.cursor import InvalidCursor, Position, decode, encode


def test_round_trips_a_position():
    position = Position(datetime(2026, 11, 3, 8, 15, 2, tzinfo=UTC), 42)

    assert decode(encode(position)) == position


@pytest.mark.parametrize(
    "raw",
    [b'["2026-11-03T08:15:02", 1]', b'["yesterday", 1]', b"[1]", b"{}", b"\xff"],
)
def test_rejects_malformed_cursors(raw):
    with pytest.raises(InvalidCursor):
        decode(base64.urlsafe_b64encode(raw).decode())
