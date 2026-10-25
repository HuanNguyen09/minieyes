import itertools
import threading

import numpy as np
import pytest
from fakes import CaptureFactory, wait_until
from prometheus_client import CollectorRegistry

from minieyes_detector.backoff import Backoff
from minieyes_detector.frame_source import FrameSource
from minieyes_detector.metrics import DetectorMetrics


def frame(n: int) -> np.ndarray:
    return np.full((2, 2, 3), n, dtype=np.uint8)


@pytest.fixture
def registry():
    return CollectorRegistry()


def start(source: FrameSource) -> threading.Thread:
    thread = threading.Thread(target=source.run, daemon=True)
    thread.start()
    return thread


def make_source(factory, registry, base=0.001):
    return FrameSource(
        "cam1",
        open_capture=factory,
        backoff=Backoff(base=base, cap=base, jitter=0.0),
        metrics=DetectorMetrics(registry),
    )


def camera_up(registry):
    return registry.get_sample_value("minieyes_camera_up", {"camera": "cam1"})


def test_failed_reads_mark_the_camera_down_and_reconnect(registry):
    factory = CaptureFactory()  # every capture fails
    source = make_source(factory, registry)
    thread = start(source)

    assert wait_until(lambda: factory.opens >= 3)
    source.stop()
    thread.join(timeout=1)

    assert camera_up(registry) == 0


def test_recovers_after_three_failures_and_marks_the_camera_up(registry):
    factory = CaptureFactory([None], [None], [None], itertools.repeat(frame(7)))
    source = make_source(factory, registry)
    thread = start(source)

    got = []
    assert wait_until(lambda: got.append(source.latest()) or got[-1] is not None)
    source.stop()
    thread.join(timeout=1)

    assert factory.opens >= 4
    assert int(got[-1][0, 0, 0]) == 7
    assert camera_up(registry) == 1


def test_stop_interrupts_a_long_backoff_wait(registry):
    factory = CaptureFactory()
    source = make_source(factory, registry, base=10.0)
    thread = start(source)
    assert wait_until(lambda: factory.opens >= 1)

    source.stop()
    thread.join(timeout=0.5)

    assert not thread.is_alive()


def test_a_slow_consumer_gets_the_newest_frame_and_older_ones_are_counted_as_dropped(registry):
    factory = CaptureFactory([frame(1), frame(2), frame(3)])
    source = make_source(factory, registry, base=10.0)
    thread = start(source)
    assert wait_until(lambda: camera_up(registry) == 0)  # stream fully read, now backing off

    newest = source.latest()
    source.stop()
    thread.join(timeout=1)

    assert int(newest[0, 0, 0]) == 3
    assert registry.get_sample_value("minieyes_frames_dropped_total", {"camera": "cam1"}) == 2


def test_latest_returns_each_frame_once_then_none_until_a_new_one_arrives(registry):
    factory = CaptureFactory([frame(1)])
    source = make_source(factory, registry, base=10.0)
    thread = start(source)
    assert wait_until(lambda: camera_up(registry) == 0)

    first, second = source.latest(), source.latest()
    source.stop()
    thread.join(timeout=1)

    assert int(first[0, 0, 0]) == 1
    assert second is None
