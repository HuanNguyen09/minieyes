import numpy as np
import pytest
from fakes import FakeClock, FakeInferenceClient, FakePublisher, FakeSource, raw_output
from prometheus_client import CollectorRegistry

from minieyes_detector.debounce import Debouncer
from minieyes_detector.inference import InferenceTimeout
from minieyes_detector.metrics import DetectorMetrics
from minieyes_detector.pipeline import Pipeline
from minieyes_detector.zones import Zone

PERSON = 0
# 640x640 frames letterbox 1:1, so model coordinates are frame coordinates
FRAME = np.zeros((640, 640, 3), dtype=np.uint8)
LANE = Zone("forklift-lane", "cam1", ((0, 300), (640, 300), (640, 640), (0, 640)))
# box (270, 300)-(370, 500): feet at (320, 500), inside the lane
INSIDE = raw_output((320, 400, 100, 200, PERSON, 0.9))
# box (270, 20)-(370, 220): feet at (320, 220), above the lane
OUTSIDE = raw_output((320, 120, 100, 200, PERSON, 0.9))


@pytest.fixture
def registry():
    return CollectorRegistry()


def make_pipeline(registry, output, frames=2, inference=None):
    source = FakeSource([FRAME] * frames)
    publisher = FakePublisher()
    pipeline = Pipeline(
        camera="cam1",
        source=source,
        inference=inference or FakeInferenceClient(output),
        zones=[LANE],
        debouncer=Debouncer(frames=2, cooldown=10.0, clock=FakeClock()),
        publisher=publisher,
        metrics=DetectorMetrics(registry),
    )
    return pipeline, publisher


def test_two_frames_with_a_person_in_the_lane_publish_exactly_one_event(registry):
    pipeline, publisher = make_pipeline(registry, INSIDE)

    pipeline.step()
    pipeline.step()

    [(camera, intrusion)] = publisher.events
    assert (camera, intrusion.zone.name) == ("cam1", "forklift-lane")
    assert intrusion.detection.bbox == (270, 300, 370, 500)


def sample(registry, name, **labels):
    return registry.get_sample_value(name, labels or None)


def test_a_person_outside_every_zone_is_counted_but_raises_no_event(registry):
    pipeline, publisher = make_pipeline(registry, OUTSIDE)

    pipeline.step()
    pipeline.step()

    assert publisher.events == []
    assert sample(registry, "minieyes_detections_total", camera="cam1") == 2


def test_frames_and_events_are_counted_per_processed_frame(registry):
    pipeline, _ = make_pipeline(registry, INSIDE, frames=3)

    processed = [pipeline.step() for _ in range(4)]  # the 4th call finds no new frame

    assert processed == [True, True, True, False]
    assert sample(registry, "minieyes_frames_total", camera="cam1") == 3
    assert sample(registry, "minieyes_detections_total", camera="cam1") == 3
    assert sample(registry, "minieyes_events_total", camera="cam1", zone="forklift-lane") == 1


def test_an_inference_failure_skips_the_frame_instead_of_crashing_the_loop(registry):
    class TimingOut:
        def infer(self, tensor):
            raise InferenceTimeout("deadline exceeded")

        def ready(self):
            return True

    pipeline, publisher = make_pipeline(registry, INSIDE, inference=TimingOut())

    assert pipeline.step() is True
    assert publisher.events == []
    assert sample(registry, "minieyes_frames_total", camera="cam1") == 0
