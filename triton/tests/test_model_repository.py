"""Model repository contract: what the detector's TritonClient expects to find."""

from pathlib import Path

from google.protobuf import text_format
from tritonclient.grpc import model_config_pb2

from scripts.export_model import install

REPO = Path(__file__).parents[1] / "model_repository"
FP32 = model_config_pb2.DataType.Value("TYPE_FP32")


def load_config() -> model_config_pb2.ModelConfig:
    text = (REPO / "yolov8n" / "config.pbtxt").read_text()
    return text_format.Parse(text, model_config_pb2.ModelConfig())


def test_config_declares_onnxruntime_with_the_yolov8_tensors():
    config = load_config()

    assert (config.name, config.backend, config.max_batch_size) == ("yolov8n", "onnxruntime", 0)
    [image] = config.input
    [output] = config.output
    assert (image.name, image.data_type, list(image.dims)) == ("images", FP32, [1, 3, 640, 640])
    assert (output.name, output.data_type, list(output.dims)) == ("output0", FP32, [1, 84, 8400])


def test_config_runs_on_cpu():
    [group] = load_config().instance_group

    assert group.kind == model_config_pb2.ModelInstanceGroup.Kind.Value("KIND_CPU")


def test_install_puts_the_exported_onnx_at_version_1(tmp_path):
    def fake_exporter(workdir: Path) -> Path:
        onnx = workdir / "yolov8n.onnx"
        onnx.write_bytes(b"onnx-bytes")
        return onnx

    target = install(fake_exporter, repository=tmp_path)

    assert target == tmp_path / "yolov8n" / "1" / "model.onnx"
    assert target.read_bytes() == b"onnx-bytes"
