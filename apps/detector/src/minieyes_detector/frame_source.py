"""Read frames from a camera on a background thread, reconnecting with backoff."""

import threading
from collections.abc import Callable
from typing import Protocol

import cv2
import numpy as np

from minieyes_detector.backoff import Backoff
from minieyes_detector.metrics import DetectorMetrics


class Capture(Protocol):
    def read(self) -> tuple[bool, np.ndarray | None]: ...
    def release(self) -> None: ...


def open_rtsp(url: str) -> Callable[[], Capture]:
    """Capture factory for a real camera; FFmpeg handles RTSP over TCP or UDP."""
    return lambda: cv2.VideoCapture(url, cv2.CAP_FFMPEG)


class FrameSource:
    def __init__(
        self,
        camera: str,
        open_capture: Callable[[], Capture],
        backoff: Backoff,
        metrics: DetectorMetrics,
    ):
        self._open = open_capture
        self._backoff = backoff
        self._up = metrics.camera_up.labels(camera=camera)
        self._dropped = metrics.frames_dropped.labels(camera=camera)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None

    def run(self) -> None:
        while not self._stop.is_set():
            capture = self._open()
            try:
                self._read_until_failure(capture)
            finally:
                capture.release()
            if self._stop.is_set():
                return
            self._up.set(0)
            self._stop.wait(self._backoff.next_delay())

    def _read_until_failure(self, capture: Capture) -> None:
        while not self._stop.is_set():
            ok, frame = capture.read()
            if not ok:
                return
            self._up.set(1)
            self._backoff.reset()
            with self._lock:
                if self._frame is not None:
                    self._dropped.inc()
                self._frame = frame

    def latest(self) -> np.ndarray | None:
        """Take the newest unread frame, or None if nothing new arrived since the last call."""
        with self._lock:
            frame, self._frame = self._frame, None
            return frame

    def stop(self) -> None:
        self._stop.set()
