"""In-memory fakes for adapters, shared by tests."""


class FakeClock:
    """Monotonic clock in seconds that only moves when a test advances it."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
