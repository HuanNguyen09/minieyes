import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import respx
from fakes import FakeClock
from prometheus_client import CollectorRegistry

from minieyes_detector.backoff import Backoff
from minieyes_detector.debounce import Intrusion
from minieyes_detector.metrics import DetectorMetrics
from minieyes_detector.publisher import Publisher
from minieyes_detector.zones import Detection, Zone

API = "https://events.example.test"
LANE = Zone("forklift-lane", "cam1", ((0, 0), (10, 0), (10, 10)))
INTRUSION = Intrusion(LANE, Detection((12.0, 40.5, 88.0, 230.0), 0.82, "person"))
FIXED_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture
def registry():
    return CollectorRegistry()


@pytest.fixture
def clock():
    return FakeClock()


def sequential_ids():
    n = iter(range(1, 10_000))
    return lambda: uuid.UUID(int=next(n))


def make_publisher(registry, clock, maxlen=1000, new_id=lambda: FIXED_ID):
    return Publisher(
        httpx.Client(base_url=API),
        api_key="site-01-key",
        site="site-01",
        backoff=Backoff(base=1.0, cap=30.0, jitter=0.0),
        metrics=DetectorMetrics(registry),
        clock=clock,
        now=lambda: datetime(2026, 11, 3, 8, 15, 2, 345000, tzinfo=UTC),
        new_id=new_id,
        maxlen=maxlen,
    )


@respx.mock
def test_the_posted_event_matches_the_prd_schema(registry, clock):
    route = respx.post(f"{API}/events").mock(return_value=httpx.Response(201))
    publisher = make_publisher(registry, clock)

    publisher.enqueue("cam1", INTRUSION)
    publisher.flush()

    assert json.loads(route.calls.last.request.content) == {
        "event_id": "00000000-0000-4000-8000-000000000001",
        "site": "site-01",
        "camera": "cam1",
        "zone": "forklift-lane",
        "type": "red_zone_intrusion",
        "confidence": 0.82,
        "bbox": [12.0, 40.5, 88.0, 230.0],
        "occurred_at": "2026-11-03T08:15:02Z",
    }


def dropped(registry, reason):
    return registry.get_sample_value("minieyes_events_dropped_total", {"reason": reason})


@respx.mock
def test_a_401_is_a_config_error_that_is_logged_counted_and_not_retried(registry, clock, caplog):
    route = respx.post(f"{API}/events").mock(return_value=httpx.Response(401))
    publisher = make_publisher(registry, clock)

    publisher.enqueue("cam1", INTRUSION)
    publisher.flush()
    clock.advance(60)
    publisher.flush()

    assert route.call_count == 1
    assert route.calls.last.request.headers["X-API-Key"] == "site-01-key"
    assert dropped(registry, "unauthorized") == 1
    assert any(r.levelname == "ERROR" and "API key" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("status", [200, 201])
@respx.mock
def test_a_200_or_201_marks_the_event_delivered(status, registry, clock):
    route = respx.post(f"{API}/events").mock(return_value=httpx.Response(status))
    publisher = make_publisher(registry, clock)

    publisher.enqueue("cam1", INTRUSION)
    publisher.flush()
    clock.advance(60)
    publisher.flush()

    assert route.call_count == 1
    assert publisher.pending == 0


@respx.mock
def test_5xx_and_connection_errors_keep_the_event_and_retry_with_backoff(registry, clock):
    route = respx.post(f"{API}/events").mock(
        side_effect=[httpx.Response(503), httpx.ConnectError("refused"), httpx.Response(201)]
    )
    publisher = make_publisher(registry, clock)
    publisher.enqueue("cam1", INTRUSION)

    calls = []
    for advance in (0, 0.5, 0.5, 1.0, 1.0):  # t = 0, 0.5, 1, 2, 3
        clock.advance(advance)
        publisher.flush()
        calls.append(route.call_count)

    # 503 at t=0 -> wait 1 s; refused at t=1 -> wait 2 s; delivered at t=3
    assert calls == [1, 1, 2, 2, 3]
    assert publisher.pending == 0
    assert registry.get_sample_value("minieyes_publish_failures_total") == 2


@respx.mock
def test_a_4xx_rejection_drops_the_event_but_429_is_retried(registry, clock):
    route = respx.post(f"{API}/events").mock(
        side_effect=[httpx.Response(422), httpx.Response(429), httpx.Response(201)]
    )
    publisher = make_publisher(registry, clock)
    publisher.enqueue("cam1", INTRUSION)  # rejected with 422
    publisher.enqueue("cam1", INTRUSION)  # throttled, then delivered

    publisher.flush()
    pending_after_throttle = publisher.pending
    clock.advance(1)
    publisher.flush()

    assert route.call_count == 3
    assert pending_after_throttle == 1
    assert publisher.pending == 0
    assert dropped(registry, "rejected") == 1


def test_a_full_buffer_drops_the_oldest_event(registry, clock):
    publisher = make_publisher(registry, clock, maxlen=3, new_id=sequential_ids())

    ids = [publisher.enqueue("cam1", INTRUSION)["event_id"] for _ in range(4)]

    assert publisher.pending == 3
    assert dropped(registry, "buffer_full") == 1
    assert ids[0].endswith("0001")


@respx.mock
def test_buffered_events_are_flushed_in_order_once_the_api_recovers(registry, clock):
    route = respx.post(f"{API}/events").mock(
        side_effect=[httpx.Response(503)] + [httpx.Response(201)] * 3
    )
    publisher = make_publisher(registry, clock, new_id=sequential_ids())
    for _ in range(3):
        publisher.enqueue("cam1", INTRUSION)

    publisher.flush()  # outage
    clock.advance(1)
    publisher.flush()  # recovered

    sent = [json.loads(c.request.content)["event_id"][-1] for c in route.calls]
    assert sent == ["1", "1", "2", "3"]
    assert publisher.pending == 0
