"""Letterbox preprocessing: fit a BGR frame into the model's square input without distortion."""

from dataclasses import dataclass

import cv2
import numpy as np

MODEL_SIZE = 640
PAD_VALUE = 114  # grey padding, as used when YOLOv8 was trained


@dataclass(frozen=True)
class Letterbox:
    scale: float
    pad_x: int
    pad_y: int
    width: int  # original frame size, used to clip boxes
    height: int

    def to_original(
        self, bbox: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        """Map an (x1, y1, x2, y2) box from model input space back to original frame pixels."""
        x1, y1, x2, y2 = bbox
        return (
            (x1 - self.pad_x) / self.scale,
            (y1 - self.pad_y) / self.scale,
            (x2 - self.pad_x) / self.scale,
            (y2 - self.pad_y) / self.scale,
        )


def letterbox(frame_bgr: np.ndarray, size: int = MODEL_SIZE) -> tuple[np.ndarray, Letterbox]:
    height, width = frame_bgr.shape[:2]
    scale = min(size / width, size / height)
    new_w, new_h = round(width * scale), round(height * scale)
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2

    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    rgb = canvas[:, :, ::-1]
    tensor = rgb.transpose(2, 0, 1)[np.newaxis].astype(np.float32) / 255.0
    return tensor, Letterbox(scale, pad_x, pad_y, width, height)
