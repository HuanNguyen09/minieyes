"""One camera's processing loop: frame -> model -> people -> red zones -> events."""

import logging
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from minieyes_detector.debounce import Debouncer, Intrusion
from minieyes_detector.inference import InferenceClient, InferenceError
from minieyes_detector.metrics import DetectorMetrics
from minieyes_detector.postprocess import postprocess
from minieyes_detector.preprocess import letterbox
from minieyes_detector.zones import Zone, evaluate

log = logging.getLogger(__name__)


class Source(Protocol):
    def latest(self) -> np.ndarray | None: ...


class EventSink(Protocol):
    def enqueue(self, camera: str, intrusion: Intrusion) -> dict: ...


class Pipeline:
    def __init__(
        self,
        camera: str,
        source: Source,
        inference: InferenceClient,
        zones: Sequence[Zone],
        debouncer: Debouncer,
        publisher: EventSink,
        metrics: DetectorMetrics,
    ):
        self._camera = camera
        self._source = source
        self._inference = inference
        self._zones = zones
        self._debouncer = debouncer
        self._publisher = publisher
        self._frames = metrics.frames.labels(camera=camera)
        self._detections = metrics.detections.labels(camera=camera)
        self._events = metrics.events

    def step(self) -> bool:
        """Process the newest frame if there is one; return whether a frame was processed."""
        frame = self._source.latest()
        if frame is None:
            return False
        tensor, transform = letterbox(frame)
        try:
            output = self._inference.infer(tensor)
        except InferenceError as e:
            log.warning("inference failed, frame skipped: %s", e, extra={"camera": self._camera})
            return True
        detections = postprocess(output, transform)
        self._frames.inc()
        self._detections.inc(len(detections))
        hits = evaluate(detections, self._zones)
        for intrusion in self._debouncer.update(self._camera, hits):
            event = self._publisher.enqueue(self._camera, intrusion)
            self._events.labels(camera=self._camera, zone=intrusion.zone.name).inc()
            log.info(
                "red-zone intrusion",
                extra={
                    "camera": self._camera,
                    "zone": intrusion.zone.name,
                    "event_id": event["event_id"],
                },
            )
        return True
