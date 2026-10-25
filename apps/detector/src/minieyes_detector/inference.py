"""Model inference behind a small interface; Triton is one adapter."""

from typing import Protocol

import numpy as np
import tritonclient.grpc as triton
from tritonclient.utils import InferenceServerException

from minieyes_detector.metrics import DetectorMetrics


class InferenceError(Exception):
    """Inference failed; the pipeline skips the frame."""


class InferenceTimeout(InferenceError):
    """The server did not answer within the client timeout."""


class InferenceClient(Protocol):
    def infer(self, tensor: np.ndarray) -> np.ndarray: ...
    def ready(self) -> bool: ...


class TritonClient:
    """InferenceClient over Triton gRPC for YOLOv8 ONNX (input `images`, output `output0`)."""

    def __init__(self, grpc, model: str, metrics: DetectorMetrics, timeout: float = 2.0):
        self._grpc = grpc
        self._model = model
        self._timeout = timeout
        self._latency = metrics.inference_seconds

    def infer(self, tensor: np.ndarray) -> np.ndarray:
        image = triton.InferInput("images", list(tensor.shape), "FP32")
        image.set_data_from_numpy(tensor.astype(np.float32, copy=False))
        try:
            with self._latency.time():
                result = self._grpc.infer(
                    self._model,
                    inputs=[image],
                    outputs=[triton.InferRequestedOutput("output0")],
                    client_timeout=self._timeout,
                )
        except InferenceServerException as e:
            if e.status() == "StatusCode.DEADLINE_EXCEEDED":
                raise InferenceTimeout(e.message()) from e
            raise InferenceError(e.message()) from e
        return result.as_numpy("output0")

    def ready(self) -> bool:
        try:
            return bool(
                self._grpc.is_server_ready(client_timeout=self._timeout)
                and self._grpc.is_model_ready(self._model, client_timeout=self._timeout)
            )
        except InferenceServerException:
            return False
