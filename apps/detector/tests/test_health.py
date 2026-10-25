from wsgiref.util import setup_testing_defaults

import pytest
from fakes import FakeClock
from prometheus_client import CollectorRegistry

from minieyes_detector.health import Heartbeat, make_app
from minieyes_detector.metrics import DetectorMetrics


def get(app, path):
    environ = {"PATH_INFO": path, "REQUEST_METHOD": "GET"}
    setup_testing_defaults(environ)
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"], captured["headers"] = status, dict(headers)

    body = b"".join(app(environ, start_response))
    return int(captured["status"].split()[0]), captured["headers"], body.decode()


@pytest.fixture
def clock():
    return FakeClock(start=1000.0)


def test_metrics_endpoint_serves_prometheus_text(clock):
    registry = CollectorRegistry()
    DetectorMetrics(registry).camera_up.labels(camera="cam1").set(1)
    app = make_app(registry, Heartbeat(clock))

    status, headers, body = get(app, "/metrics")

    assert status == 200
    assert headers["Content-Type"].startswith("text/plain")
    assert 'minieyes_camera_up{camera="cam1"} 1.0' in body


@pytest.mark.parametrize(("seconds_since_beat", "expected"), [(0, 200), (30, 200), (30.1, 503)])
def test_healthz_fails_once_the_main_loop_heartbeat_is_older_than_30s(
    seconds_since_beat, expected, clock
):
    heartbeat = Heartbeat(clock)
    app = make_app(CollectorRegistry(), heartbeat)
    heartbeat.beat()

    clock.advance(seconds_since_beat)
    status, _, _ = get(app, "/healthz")

    assert status == expected
