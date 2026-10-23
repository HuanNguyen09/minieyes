import numpy as np
import pytest

from minieyes_detector.postprocess import postprocess
from minieyes_detector.preprocess import Letterbox

PERSON, CAR = 0, 2
IDENTITY = Letterbox(scale=1.0, pad_x=0, pad_y=0, width=640, height=640)


def raw_output(*candidates):
    """Build a YOLOv8 output tensor (1, 84, 8400) from (cx, cy, w, h, class_id, score) tuples."""
    out = np.zeros((1, 84, 8400), dtype=np.float32)
    for i, (cx, cy, w, h, cls, score) in enumerate(candidates):
        out[0, 0:4, i] = (cx, cy, w, h)
        out[0, 4 + cls, i] = score
    return out


def test_person_candidate_is_decoded_from_centre_size_to_corners():
    detections = postprocess(raw_output((320, 320, 100, 200, PERSON, 0.9)), IDENTITY)

    assert len(detections) == 1
    assert detections[0].bbox == (270, 220, 370, 420)
    assert detections[0].label == "person"
    assert detections[0].confidence == pytest.approx(0.9)


def test_only_the_person_class_is_kept():
    detections = postprocess(
        raw_output((100, 100, 50, 50, CAR, 0.95), (400, 300, 60, 120, PERSON, 0.8)), IDENTITY
    )

    assert [d.bbox for d in detections] == [(370, 240, 430, 360)]


def test_candidates_below_the_confidence_threshold_are_dropped():
    raw = raw_output((100, 100, 40, 80, PERSON, 0.39), (400, 300, 40, 80, PERSON, 0.41))

    assert [d.confidence for d in postprocess(raw, IDENTITY)] == [pytest.approx(0.41)]
    assert postprocess(raw, IDENTITY, conf_threshold=0.5) == []


def test_overlapping_boxes_are_suppressed_keeping_the_highest_score():
    raw = raw_output(
        (300, 300, 100, 200, PERSON, 0.9),  # A
        (305, 302, 100, 200, PERSON, 0.7),  # nearly the same box as A -> suppressed
        (100, 100, 50, 100, PERSON, 0.8),  # separate person -> kept
    )

    detections = postprocess(raw, IDENTITY)

    assert [d.bbox for d in detections] == [(250, 200, 350, 400), (75, 50, 125, 150)]


def test_boxes_are_mapped_back_through_the_letterbox_transform():
    hd = Letterbox(scale=0.5, pad_x=0, pad_y=140, width=1280, height=720)
    # model-space box (250, 240, 350, 440) -> original (500, 200, 700, 600)
    raw = raw_output((300, 340, 100, 200, PERSON, 0.9))

    assert [d.bbox for d in postprocess(raw, hd)] == [(500, 200, 700, 600)]


def test_boxes_are_clipped_to_the_frame():
    raw = raw_output((20, 600, 100, 200, PERSON, 0.9))  # spills past left and bottom edges

    assert [d.bbox for d in postprocess(raw, IDENTITY)] == [(0, 500, 70, 640)]


def test_empty_output_yields_no_detections():
    assert postprocess(np.zeros((1, 84, 8400), dtype=np.float32), IDENTITY) == []
