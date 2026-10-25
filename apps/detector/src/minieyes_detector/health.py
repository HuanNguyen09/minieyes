"""HTTP endpoints for Prometheus scraping and Kubernetes probes."""

from prometheus_client import CollectorRegistry, make_wsgi_app

from minieyes_detector.debounce import Clock


class Heartbeat:
    """The main loop calls beat() once per iteration; a stale heartbeat means it is stuck."""

    def __init__(self, clock: Clock):
        self._clock = clock
        self._last = clock()

    def beat(self) -> None:
        self._last = self._clock()

    def age(self) -> float:
        return self._clock() - self._last


def make_app(registry: CollectorRegistry, heartbeat: Heartbeat, max_age: float = 30.0):
    metrics = make_wsgi_app(registry)

    def app(environ, start_response):
        if environ.get("PATH_INFO") == "/healthz":
            age = heartbeat.age()
            ok = age <= max_age
            status = "200 OK" if ok else "503 Service Unavailable"
            start_response(status, [("Content-Type", "text/plain")])
            return [f"{'ok' if ok else 'stale'}: last loop {age:.1f}s ago\n".encode()]
        return metrics(environ, start_response)

    return app
