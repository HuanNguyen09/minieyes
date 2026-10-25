"""Smoke test against a running server that speaks the KServe v2 protocol: Triton in
production, OpenVINO Model Server in local compose and CI (ADR 005).

    TRITON_HTTP_URL=http://localhost:8000 TRITON_URL=localhost:8001 pytest triton -m integration
"""

import os
import urllib.request

import numpy as np
import pytest
import tritonclient.grpc as triton
from prometheus_client import CollectorRegistry

from minieyes_detector.inference import TritonClient
from minieyes_detector.metrics import DetectorMetrics

HTTP_URL = os.environ.get("TRITON_HTTP_URL")
GRPC_URL = os.environ.get("TRITON_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (HTTP_URL and GRPC_URL), reason="TRITON_HTTP_URL/TRITON_URL not set"),
]


def test_server_reports_ready_over_http():
    with urllib.request.urlopen(f"{HTTP_URL}/v2/health/ready", timeout=5) as response:
        assert response.status == 200


def test_a_blank_image_returns_84_by_8400_candidates():
    client = TritonClient(
        triton.InferenceServerClient(GRPC_URL), "yolov8n", DetectorMetrics(CollectorRegistry())
    )

    assert client.ready()
    output = client.infer(np.zeros((1, 3, 640, 640), dtype=np.float32))

    assert output.shape == (1, 84, 8400)
