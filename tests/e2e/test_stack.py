"""End-to-end tests against the compose stack (#17).

    docker compose up -d --build
    uv run --no-project --with pytest --with httpx pytest tests/e2e -m e2e

They stop and start containers, so do not run them against a stack you are using.
"""

import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[2]
API = "http://localhost:18000"
DETECTOR = "http://localhost:18080"
KEY = {"X-API-Key": "demo-site-01-key"}
ZONE = "walkway"

pytestmark = pytest.mark.e2e


def compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, capture_output=True)


def wait_for(predicate, timeout: float, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if value := predicate():
                return value
        except httpx.HTTPError:
            pass
        time.sleep(interval)
    return None


def metric(name: str, **labels: str) -> float:
    """Sum of every sample of `name` whose labels include `labels`; 0 if there is none yet."""
    total = 0.0
    for line in httpx.get(f"{DETECTOR}/metrics", timeout=5).text.splitlines():
        if not line.startswith(name) or line.startswith("#"):
            continue
        series, value = line.rsplit(" ", 1)
        if series.split("{")[0] == name and all(f'{k}="{v}"' in series for k, v in labels.items()):
            total += float(value)
    return total


def stored_events() -> int:
    count, cursor = 0, None
    while True:
        params = {"limit": 500} | ({"cursor": cursor} if cursor else {})
        page = httpx.get(f"{API}/events", params=params, headers=KEY, timeout=5).json()
        count += len(page["items"])
        cursor = page["next"]
        if cursor is None:
            return count


@pytest.fixture(autouse=True)
def stack_running():
    compose("start", "camera-sim", "event-api")
    assert wait_for(lambda: httpx.get(f"{API}/readyz", timeout=2).status_code == 200, 60)
    assert wait_for(lambda: metric("minieyes_camera_up", camera="cam1") == 1, 90)


def test_an_intrusion_reaches_the_event_api_within_60_seconds():
    def intrusion():
        page = httpx.get(f"{API}/events", params={"zone": ZONE}, headers=KEY, timeout=5).json()
        return [e for e in page["items"] if e["type"] == "red_zone_intrusion"]

    assert wait_for(intrusion, 60)


def test_camera_down_is_reported_within_30_seconds_and_recovers():
    compose("stop", "camera-sim")
    down = wait_for(lambda: metric("minieyes_camera_up", camera="cam1") == 0, 30)
    compose("start", "camera-sim")
    # the detector retries with backoff capped at 30 s
    up = wait_for(lambda: metric("minieyes_camera_up", camera="cam1") == 1, 60)

    assert down and up


def test_no_event_is_lost_while_the_event_api_is_down_for_30_seconds():
    compose("stop", "event-api")
    time.sleep(30)
    raised_during_outage = metric("minieyes_events_total")
    compose("start", "event-api")
    assert wait_for(lambda: httpx.get(f"{API}/readyz", timeout=2).status_code == 200, 60)

    # freeze the input so the totals stop moving, then let the buffer drain
    compose("stop", "camera-sim")

    def delivered_everything():
        expected = metric("minieyes_events_total") - metric("minieyes_events_dropped_total")
        return stored_events() == expected

    assert raised_during_outage > 0
    assert wait_for(delivered_everything, 90, interval=3)
