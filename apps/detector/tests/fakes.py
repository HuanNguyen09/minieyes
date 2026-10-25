"""In-memory fakes for adapters, shared by tests."""


class FakeClock:
    """Monotonic clock in seconds that only moves when a test advances it."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeCapture:
    """Stands in for cv2.VideoCapture: replays an iterable of frames.

    None, or the end of the iterable, is a failed read, like a dropped stream.
    """

    def __init__(self, script):
        self._frames = iter(script)
        self.released = False

    def read(self):
        frame = next(self._frames, None)
        return (frame is not None), frame

    def release(self) -> None:
        self.released = True


class CaptureFactory:
    """Hands out one FakeCapture per (re)connect and counts the opens."""

    def __init__(self, *scripts):
        self._scripts = list(scripts)
        self.opens = 0

    def __call__(self) -> FakeCapture:
        self.opens += 1
        return FakeCapture(self._scripts.pop(0) if self._scripts else [])


def wait_until(predicate, timeout: float = 2.0) -> bool:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False
