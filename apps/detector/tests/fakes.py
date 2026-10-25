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


class FakeInferenceClient:
    """InferenceClient that returns a fixed output and remembers each input."""

    def __init__(self, output, ready: bool = True):
        self._output = output
        self._ready = ready
        self.calls = []

    def infer(self, tensor):
        self.calls.append(tensor)
        return self._output

    def ready(self) -> bool:
        return self._ready


class FakeTritonResult:
    def __init__(self, outputs):
        self._outputs = outputs

    def as_numpy(self, name):
        return self._outputs.get(name)


class FakeTritonGrpc:
    """Stands in for tritonclient.grpc.InferenceServerClient.

    `error` is raised from infer(); readiness flags drive is_server_ready / is_model_ready,
    and an exception given as server_ready is raised, like an unreachable server.
    """

    def __init__(self, outputs=None, error=None, server_ready=True, model_ready=True):
        self._outputs = outputs or {}
        self._error = error
        self._server_ready = server_ready
        self._model_ready = model_ready
        self.requests = []

    def infer(self, model_name, inputs, outputs=None, client_timeout=None, **_):
        self.requests.append(
            {"model": model_name, "inputs": inputs, "outputs": outputs, "timeout": client_timeout}
        )
        if self._error is not None:
            raise self._error
        return FakeTritonResult(self._outputs)

    def is_server_ready(self, **_):
        if isinstance(self._server_ready, Exception):
            raise self._server_ready
        return self._server_ready

    def is_model_ready(self, model_name, **_):
        return self._model_ready
