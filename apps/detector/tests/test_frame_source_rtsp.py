"""Real OpenCV adapter against the camera-sim stream (#16): CAMERA_SIM_URL=rtsp://localhost:8554/cam1."""

import os
import threading

import pytest
from fakes import wait_until
from prometheus_client import CollectorRegistry

from minieyes_detector.backoff import Backoff
from minieyes_detector.frame_source import FrameSource, open_rtsp
from minieyes_detector.metrics import DetectorMetrics

URL = os.environ.get("CAMERA_SIM_URL")


@pytest.mark.integration
@pytest.mark.skipif(not URL, reason="CAMERA_SIM_URL not set")
def test_reads_bgr_frames_from_the_camera_simulator():
    source = FrameSource("cam1", open_rtsp(URL), Backoff(), DetectorMetrics(CollectorRegistry()))
    thread = threading.Thread(target=source.run, daemon=True)
    thread.start()

    got = []
    assert wait_until(lambda: got.append(source.latest()) or got[-1] is not None, timeout=15)
    source.stop()
    thread.join(timeout=5)

    assert got[-1].ndim == 3 and got[-1].shape[2] == 3
