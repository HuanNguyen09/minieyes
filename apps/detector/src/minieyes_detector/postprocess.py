"""Turn raw YOLOv8 output (1, 84, 8400) into person detections in original frame pixels."""

import cv2
import numpy as np

from minieyes_detector.preprocess import Letterbox
from minieyes_detector.zones import Detection

PERSON_CLASS = 0


def postprocess(
    output: np.ndarray,
    transform: Letterbox,
    conf_threshold: float = 0.4,
    iou_threshold: float = 0.5,
) -> list[Detection]:
    preds = output[0].T  # (8400, 84): cx, cy, w, h, 80 class scores
    class_ids = preds[:, 4:].argmax(axis=1)
    scores = preds[:, 4:].max(axis=1)
    keep = (class_ids == PERSON_CLASS) & (scores >= conf_threshold)
    boxes_cxcywh, scores = preds[keep, :4], scores[keep]
    if len(scores) == 0:
        return []

    # NMSBoxes wants top-left x, y, width, height
    xywh = boxes_cxcywh.copy()
    xywh[:, 0] -= xywh[:, 2] / 2
    xywh[:, 1] -= xywh[:, 3] / 2
    kept = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), conf_threshold, iou_threshold)

    detections = []
    for i in sorted(np.array(kept).flatten(), key=lambda i: -scores[i]):
        x, y, w, h = xywh[i]
        x1, y1, x2, y2 = transform.to_original((float(x), float(y), float(x + w), float(y + h)))
        box = (
            min(max(x1, 0.0), transform.width),
            min(max(y1, 0.0), transform.height),
            min(max(x2, 0.0), transform.width),
            min(max(y2, 0.0), transform.height),
        )
        detections.append(Detection(box, float(scores[i]), "person"))
    return detections
