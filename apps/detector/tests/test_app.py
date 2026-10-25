import itertools
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request

import httpx
import numpy as np
import pytest
import respx
from fakes import CaptureFactory, FakeTritonGrpc, raw_output, wait_until
from prometheus_client import CollectorRegistry

from minieyes_detector.app import build
from minieyes_detector.settings import Settings

FRAME = np.zeros((640, 640, 3), dtype=np.uint8)
ZONES = """
cameras:
  cam1:
    zones:
      - name: forklift-lane
        polygon: [[0, 300], [640, 300], [640, 640], [0, 640]]
"""


def settings(tmp_path, **overrides):
    zones = tmp_path / "zones.yaml"
    zones.write_text(ZONES)
    env = {
        "MINIEYES_SITE": "site-01",
        "MINIEYES_CAMERAS": "cam1=rtsp://camera-sim:8554/cam1",
        "MINIEYES_EVENT_API_URL": "https://events.example.test",
        "MINIEYES_API_KEY": "k",
        "MINIEYES_ZONES_FILE": str(zones),
        "MINIEYES_COOLDOWN_SECONDS": "3600",
    }
    return Settings.from_env(env | overrides)


@respx.mock
def test_the_assembled_detector_delivers_an_intrusion_to_the_event_api(tmp_path):
    api = respx.post("https://events.example.test/events").mock(return_value=httpx.Response(201))
    detector = build(
        settings(tmp_path),
        registry=CollectorRegistry(),
        open_capture=lambda url: CaptureFactory(itertools.repeat(FRAME)),
        grpc=FakeTritonGrpc(outputs={"output0": raw_output((320, 400, 100, 200, 0, 0.9))}),
    )
    stop = threading.Event()
    thread = threading.Thread(target=detector.run, args=(stop,), daemon=True)
    thread.start()

    delivered = wait_until(lambda: api.call_count >= 1, timeout=5)
    stop.set()
    thread.join(timeout=5)

    assert delivered
    assert not thread.is_alive()
    event = json.loads(api.calls.last.request.content)
    assert (event["site"], event["camera"], event["zone"]) == ("site-01", "cam1", "forklift-lane")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.integration  # spawns a fresh interpreter: cv2 + tritonclient imports take seconds
def test_python_m_minieyes_detector_serves_health_and_metrics(tmp_path):
    port = free_port()
    zones = tmp_path / "zones.yaml"
    zones.write_text(ZONES)
    env = os.environ | {
        "MINIEYES_SITE": "site-01",
        # unreachable camera and Triton: the process must still come up and report itself
        "MINIEYES_CAMERAS": f"cam1={tmp_path / 'missing.mp4'}",
        "MINIEYES_EVENT_API_URL": "http://127.0.0.1:9",
        "MINIEYES_API_KEY": "k",
        "MINIEYES_TRITON_URL": "127.0.0.1:9",
        "MINIEYES_ZONES_FILE": str(zones),
        "MINIEYES_HTTP_PORT": str(port),
    }
    log_file = tmp_path / "detector.log"
    with log_file.open("w") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "minieyes_detector"], env=env, stdout=out, stderr=out
        )
    try:

        def get(path):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1) as r:
                    return r.status, r.read().decode()
            except OSError:
                return None, ""

        healthy = wait_until(lambda: get("/healthz")[0] == 200, timeout=60)
        assert healthy, f"exit={proc.poll()}\n{log_file.read_text()[-2000:]}"
        status, body = get("/metrics")
        assert status == 200
        assert 'minieyes_camera_up{camera="cam1"} 0.0' in body
    finally:
        proc.terminate()
        proc.wait(timeout=10)
