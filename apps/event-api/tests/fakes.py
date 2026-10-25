"""In-memory fakes for adapters, shared by tests."""

from datetime import UTC, datetime, timedelta


class FakeNow:
    """Wall clock returning a fixed aware datetime that only moves when a test advances it."""

    def __init__(self, start: datetime = datetime(2026, 11, 3, 8, 15, 5, tzinfo=UTC)):
        self.value = start

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)
