"""Deliver intrusion events to the Event API, buffering them through short outages."""

import logging
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from minieyes_detector.backoff import Backoff
from minieyes_detector.debounce import Clock, Intrusion
from minieyes_detector.metrics import DetectorMetrics

log = logging.getLogger(__name__)


class Publisher:
    def __init__(
        self,
        http: httpx.Client,
        api_key: str,
        site: str,
        backoff: Backoff,
        metrics: DetectorMetrics,
        clock: Clock,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
        maxlen: int = 1000,
    ):
        self._http = http
        self._api_key = api_key
        self._site = site
        self._now = now
        self._new_id = new_id
        self._backoff = backoff
        self._clock = clock
        self._retry_at = float("-inf")
        self._dropped = metrics.events_dropped
        self._failures = metrics.publish_failures
        self._maxlen = maxlen
        self._buffer: deque[dict] = deque()

    def enqueue(self, camera: str, intrusion: Intrusion) -> dict:
        event = {
            "event_id": str(self._new_id()),
            "site": self._site,
            "camera": camera,
            "zone": intrusion.zone.name,
            "type": "red_zone_intrusion",
            "confidence": intrusion.detection.confidence,
            "bbox": list(intrusion.detection.bbox),
            "occurred_at": self._now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if len(self._buffer) >= self._maxlen:
            self._buffer.popleft()
            self._dropped.labels(reason="buffer_full").inc()
        self._buffer.append(event)
        return event

    @property
    def pending(self) -> int:
        return len(self._buffer)

    def flush(self) -> None:
        """Send buffered events oldest first; stop at the first failure worth retrying."""
        if self._clock() < self._retry_at:
            return
        while self._buffer:
            event = self._buffer[0]
            try:
                response = self._http.post(
                    "/events", json=event, headers={"X-API-Key": self._api_key}
                )
            except httpx.TransportError:
                self._retry_later()
                return
            status = response.status_code
            if status >= 500 or status == 429:
                self._retry_later()
                return
            self._buffer.popleft()
            self._backoff.reset()
            if status == 401:
                log.error("Event API rejected the API key for site %s", self._site)
                self._dropped.labels(reason="unauthorized").inc()
            elif status >= 400:
                log.warning("Event API rejected event %s: %s", event["event_id"], status)
                self._dropped.labels(reason="rejected").inc()

    def _retry_later(self) -> None:
        self._failures.inc()
        self._retry_at = self._clock() + self._backoff.next_delay()
