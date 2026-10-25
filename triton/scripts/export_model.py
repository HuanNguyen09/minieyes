"""Export YOLOv8n to ONNX and install it into the Triton model repository.

Run from the repo root (downloads yolov8n.pt and a CPU build of torch into a throwaway env):

    uv run --no-project --python 3.12 --with ultralytics==8.3.40 --with torch==2.5.1 \
        --with torchvision==0.20.1 --with onnx==1.17.0 --with onnxslim==0.1.42 \
        python triton/scripts/export_model.py

YOLOv8 is AGPL-3.0 (PRD §13); the .pt and .onnx files are never committed.
"""

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

REPOSITORY = Path(__file__).parents[1] / "model_repository"
MODEL = "yolov8n"

Exporter = Callable[[Path], Path]


def ultralytics_exporter(workdir: Path) -> Path:
    from ultralytics import YOLO  # heavy (torch); only needed for a real export

    model = YOLO(str(workdir / f"{MODEL}.pt"))  # downloads the official weights
    return Path(model.export(format="onnx", imgsz=640, opset=12, dynamic=False, simplify=True))


def install(exporter: Exporter, repository: Path = REPOSITORY) -> Path:
    """Run the exporter in a temp dir; copy its ONNX file to <repository>/yolov8n/1/model.onnx."""
    target = repository / MODEL / "1" / "model.onnx"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(exporter(Path(tmp)), target)
    return target


if __name__ == "__main__":
    print(f"wrote {install(ultralytics_exporter)}")
