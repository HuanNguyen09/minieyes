# ADR-005 — OpenVINO Model Server stands in for Triton locally and in CI

**Status:** Accepted

## Context

Production inference runs on NVIDIA Triton (PRD FR-TRI). The official Triton image is about
15 GB unpacked. The development laptop has about 20 GB free and GitHub-hosted runners about
14 GB, so pulling Triton for `docker compose` and the e2e job is not practical.

The detector talks to the model server only through `tritonclient.grpc` (KServe v2 protocol:
`ServerReady`, `ModelReady`, `ModelInfer`), wrapped by `InferenceClient`.

## Decision

- **Edge and cloud clusters:** Triton, image pinned once in `charts/triton/values.yaml`, model repository
  `triton/model_repository/` with `config.pbtxt` (onnxruntime backend, CPU).
- **Local compose and CI e2e:** OpenVINO Model Server (`openvino/model_server`, about 0.3 GB),
  serving the same `model.onnx` with the same tensor names (`images`, `output0`) over the same
  KServe v2 gRPC and HTTP endpoints.
- `triton/tests/test_smoke.py` runs unchanged against either server.

## Consequences

- The detector code and its `TritonClient` are identical in every environment.
- Triton-specific behaviour (config.pbtxt parsing, onnxruntime backend, Triton metrics such as
  `nv_inference_*`) is only exercised on the edge. The edge smoke test after each deploy covers it.
- Latency numbers from compose are not representative of Triton; benchmark on the edge node.
