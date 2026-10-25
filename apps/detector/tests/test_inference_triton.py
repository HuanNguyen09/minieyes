"""Real Triton serving the YOLOv8n ONNX model: TRITON_URL=localhost:8001."""

import os

import numpy as np
import pytest
import tritonclient.grpc as triton
from prometheus_client import CollectorRegistry

from minieyes_detector.inference import TritonClient
from minieyes_detector.metrics import DetectorMetrics

URL = os.environ.get("TRITON_URL")


@pytest.mark.integration
@pytest.mark.skipif(not URL, reason="TRITON_URL not set")
def test_yolov8n_returns_84_by_8400_candidates():
    client = TritonClient(
        triton.InferenceServerClient(URL), "yolov8n", DetectorMetrics(CollectorRegistry())
    )

    assert client.ready()
    output = client.infer(np.zeros((1, 3, 640, 640), dtype=np.float32))

    assert output.shape == (1, 84, 8400)
