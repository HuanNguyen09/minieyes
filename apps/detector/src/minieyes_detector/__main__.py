"""`python -m minieyes_detector`: run the detector until SIGTERM/SIGINT."""

import logging
import os
import signal
import sys
import threading

from prometheus_client import REGISTRY

from minieyes_detector import logs
from minieyes_detector.app import build, serve
from minieyes_detector.settings import Settings, SettingsError


def main() -> int:
    try:
        settings = Settings.from_env(os.environ)
    except SettingsError as e:
        print(f"minieyes-detector: {e}", file=sys.stderr)
        return 2
    logs.configure(settings.log_level)
    log = logging.getLogger("minieyes_detector")

    detector = build(settings, registry=REGISTRY)
    server = serve(detector.wsgi_app, settings.http_port)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    log.info(
        "detector started",
        extra={"camera": ",".join(settings.cameras)},
    )
    try:
        detector.run(stop)
    finally:
        server.shutdown()
    log.info("detector stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
