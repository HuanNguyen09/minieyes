"""Detector metrics, named and labelled as in PRD §7.2."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


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
        # no camera label: one Triton client serves every camera
        self.inference_seconds = Histogram(
            "minieyes_inference_seconds",
            "Round-trip time of one Triton inference",
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
            registry=registry,
        )
