"""Detector metrics, named and labelled as in PRD §7.2."""

from prometheus_client import CollectorRegistry, Counter, Gauge


class DetectorMetrics:
    def __init__(self, registry: CollectorRegistry):
        self.camera_up = Gauge(
            "minieyes_camera_up",
            "1 while the camera stream is readable",
            ["camera"],
            registry=registry,
        )
        self.frames_dropped = Counter(
            "minieyes_frames_dropped_total",
            "Frames overwritten before the pipeline consumed them",
            ["camera"],
            registry=registry,
        )
