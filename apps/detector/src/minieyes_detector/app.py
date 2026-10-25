"""Wire settings, adapters and pipelines into a runnable detector."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import httpx
import tritonclient.grpc as triton
from prometheus_client import CollectorRegistry

from minieyes_detector.backoff import Backoff
from minieyes_detector.debounce import Clock, Debouncer
from minieyes_detector.frame_source import Capture, FrameSource, open_rtsp
from minieyes_detector.health import Heartbeat, make_app
from minieyes_detector.inference import TritonClient
from minieyes_detector.metrics import DetectorMetrics
from minieyes_detector.pipeline import Pipeline
from minieyes_detector.publisher import Publisher
from minieyes_detector.settings import Settings
from minieyes_detector.zones import load_zones

log = logging.getLogger(__name__)

IDLE_WAIT = 0.01  # seconds to sleep when no camera had a new frame


@dataclass
class Detector:
    sources: list[FrameSource]
    pipelines: list[Pipeline]
    publisher: Publisher
    heartbeat: Heartbeat
    inference: TritonClient
    wsgi_app: Callable

    def run(self, stop: threading.Event) -> None:
        """Main loop: start one reader thread per camera, process frames until stop is set."""
        threads = [threading.Thread(target=s.run, daemon=True) for s in self.sources]
        for t in threads:
            t.start()
        if not self.inference.ready():
            log.warning("Triton is not ready yet; frames are skipped until it is")
        try:
            while not stop.is_set():
                busy = [p.step() for p in self.pipelines]
                self.publisher.flush()
                self.heartbeat.beat()
                if not any(busy):
                    stop.wait(IDLE_WAIT)
        finally:
            for s in self.sources:
                s.stop()
            for t in threads:
                t.join(timeout=5)


def build(
    settings: Settings,
    registry: CollectorRegistry,
    clock: Clock = time.monotonic,
    open_capture: Callable[[str], Callable[[], Capture]] = open_rtsp,
    grpc=None,
    http: httpx.Client | None = None,
) -> Detector:
    metrics = DetectorMetrics(registry)
    zones = load_zones(Path(settings.zones_file).read_text())
    inference = TritonClient(
        grpc or triton.InferenceServerClient(settings.triton_url), settings.model, metrics
    )
    publisher = Publisher(
        http or httpx.Client(base_url=settings.event_api_url, timeout=5.0),
        api_key=settings.api_key,
        site=settings.site,
        backoff=Backoff(),
        metrics=metrics,
        clock=clock,
    )
    debouncer = Debouncer(settings.debounce_frames, settings.cooldown_seconds, clock)
    sources, pipelines = [], []
    for camera, url in settings.cameras.items():
        source = FrameSource(camera, open_capture(url), Backoff(), metrics)
        sources.append(source)
        pipelines.append(
            Pipeline(
                camera, source, inference, zones.get(camera, []), debouncer, publisher, metrics
            )
        )
    heartbeat = Heartbeat(clock)
    return Detector(
        sources, pipelines, publisher, heartbeat, inference, make_app(registry, heartbeat)
    )


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # probes every few seconds would flood the logs
        pass


def serve(app: Callable, port: int) -> WSGIServer:
    server = make_server("0.0.0.0", port, app, handler_class=_QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
