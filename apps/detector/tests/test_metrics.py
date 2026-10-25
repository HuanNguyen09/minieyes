from prometheus_client import CollectorRegistry

from minieyes_detector.metrics import DetectorMetrics

# PRD §7.2, copied by hand: the alert rules and dashboards depend on these exact names
CONTRACT = {
    ("minieyes_camera_up", "gauge", ("camera",)),
    ("minieyes_frames_total", "counter", ("camera",)),
    ("minieyes_frames_dropped_total", "counter", ("camera",)),
    ("minieyes_inference_seconds", "histogram", ()),
    ("minieyes_detections_total", "counter", ("camera",)),
    ("minieyes_events_total", "counter", ("camera", "zone")),
    ("minieyes_events_dropped_total", "counter", ("reason",)),
    ("minieyes_publish_failures_total", "counter", ()),
}


def exposed(metrics: DetectorMetrics):
    found = set()
    for metric in vars(metrics).values():
        name = metric._name + ("_total" if metric._type == "counter" else "")
        found.add((name, metric._type, tuple(metric._labelnames)))
    return found


def test_registry_matches_the_prd_metrics_contract_exactly():
    assert exposed(DetectorMetrics(CollectorRegistry())) == CONTRACT
