import numpy as np
import pytest
from fakes import FakeInferenceClient, FakeTritonGrpc
from prometheus_client import CollectorRegistry
from tritonclient.utils import InferenceServerException

from minieyes_detector.inference import (
    InferenceClient,
    InferenceError,
    InferenceTimeout,
    TritonClient,
)
from minieyes_detector.metrics import DetectorMetrics

TENSOR = np.zeros((1, 3, 640, 640), dtype=np.float32)


@pytest.fixture
def registry():
    return CollectorRegistry()


def test_fake_client_returns_the_configured_output_and_records_calls():
    output = np.ones((1, 84, 8400), dtype=np.float32)
    client: InferenceClient = FakeInferenceClient(output)

    result = client.infer(TENSOR)

    assert result is output
    assert client.calls == [TENSOR]
    assert client.ready()


def test_triton_adapter_sends_images_fp32_and_reads_output0(registry):
    output = np.ones((1, 84, 8400), dtype=np.float32)
    grpc = FakeTritonGrpc(outputs={"output0": output})
    client = TritonClient(grpc, model="yolov8n", metrics=DetectorMetrics(registry), timeout=2.0)

    result = client.infer(TENSOR)

    [request] = grpc.requests
    [image] = request["inputs"]
    assert (request["model"], request["timeout"]) == ("yolov8n", 2.0)
    assert (image.name(), image.shape(), image.datatype()) == ("images", [1, 3, 640, 640], "FP32")
    assert [o.name() for o in request["outputs"]] == ["output0"]
    np.testing.assert_array_equal(result, output)


def test_a_deadline_exceeded_becomes_inference_timeout(registry):
    error = InferenceServerException("Deadline Exceeded", status="StatusCode.DEADLINE_EXCEEDED")
    client = TritonClient(FakeTritonGrpc(error=error), "yolov8n", DetectorMetrics(registry))

    with pytest.raises(InferenceTimeout):
        client.infer(TENSOR)


def test_other_server_errors_become_inference_error(registry):
    error = InferenceServerException("model not found", status="StatusCode.NOT_FOUND")
    client = TritonClient(FakeTritonGrpc(error=error), "yolov8n", DetectorMetrics(registry))

    with pytest.raises(InferenceError) as raised:
        client.infer(TENSOR)

    assert not isinstance(raised.value, InferenceTimeout)


@pytest.mark.parametrize(
    ("grpc", "expected"),
    [
        (FakeTritonGrpc(), True),
        (FakeTritonGrpc(server_ready=False), False),
        (FakeTritonGrpc(model_ready=False), False),
        (FakeTritonGrpc(server_ready=InferenceServerException("connection refused")), False),
    ],
    ids=["ready", "server-not-ready", "model-not-ready", "unreachable"],
)
def test_ready_needs_both_server_and_model(grpc, expected, registry):
    client = TritonClient(grpc, "yolov8n", DetectorMetrics(registry))

    assert client.ready() is expected


def test_each_inference_is_observed_into_the_latency_histogram(registry):
    grpc = FakeTritonGrpc(outputs={"output0": np.ones((1, 84, 8400), dtype=np.float32)})
    client = TritonClient(grpc, "yolov8n", DetectorMetrics(registry))

    client.infer(TENSOR)
    client.infer(TENSOR)

    assert registry.get_sample_value("minieyes_inference_seconds_count") == 2
