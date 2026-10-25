# ruff: noqa: E501  (PromQL strings read better unbroken)
"""Generate the Grafana dashboards in observability/dashboards/ (#35).

    python observability/scripts/build_dashboards.py          # write the JSON files
    python observability/scripts/build_dashboards.py --check  # fail if they are out of date

Queries use only PRD §7.2 metrics (and the API's minieyes_api_*); edge series carry `site`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "dashboards"
DS = {"type": "prometheus", "uid": "prometheus"}
SITE = 'site=~"$site"'
CAM = 'site=~"$site", camera=~"$camera"'


def panel(
    pid: int,
    title: str,
    expr: str,
    legend: str,
    x: int,
    y: int,
    *,
    kind: str = "timeseries",
    unit: str = "short",
    w: int = 12,
    h: int = 8,
) -> dict:
    return {
        "id": pid,
        "type": kind,
        "title": title,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}}
        if kind == "timeseries"
        else {},
        "targets": [{"refId": "A", "expr": expr, "legendFormat": legend, "datasource": DS}],
    }


def variable(name: str, query: str, *, multi: bool = True) -> dict:
    return {
        "name": name,
        "type": "query",
        "datasource": DS,
        "query": {"query": query, "refId": f"{name}-values"},
        "refresh": 2,
        "includeAll": True,
        "multi": multi,
        "current": {"text": "All", "value": "$__all"},
    }


def dashboard(uid: str, title: str, panels: list[dict], variables: list[dict]) -> dict:
    return {
        "uid": uid,
        "title": title,
        "tags": ["minieyes"],
        "timezone": "browser",
        "refresh": "30s",
        "time": {"from": "now-6h", "to": "now"},
        "schemaVersion": 39,
        "templating": {"list": variables},
        "panels": panels,
    }


def fleet() -> dict:
    return dashboard(
        "minieyes-fleet",
        "MiniEyes / Fleet",
        [
            panel(
                1,
                "Cameras up",
                f"sum by (site) (minieyes_camera_up{{{SITE}}})",
                "{{site}}",
                0,
                0,
                kind="stat",
                w=6,
            ),
            panel(
                2,
                "Edge targets up",
                f"sum by (site) (up{{{SITE}}})",
                "{{site}}",
                6,
                0,
                kind="stat",
                w=6,
            ),
            panel(
                3,
                "Intrusions (1h)",
                f"sum by (site) (increase(minieyes_events_total{{{SITE}}}[1h]))",
                "{{site}}",
                12,
                0,
                kind="stat",
                w=6,
            ),
            panel(
                4,
                "Events dropped (1h)",
                f"sum by (site, reason) (increase(minieyes_events_dropped_total{{{SITE}}}[1h]))",
                "{{site}} {{reason}}",
                18,
                0,
                kind="stat",
                w=6,
            ),
            panel(
                5,
                "Frames per second",
                f"sum by (site) (rate(minieyes_frames_total{{{SITE}}}[2m]))",
                "{{site}}",
                0,
                4,
                unit="fps",
            ),
            panel(
                6,
                "Publish failures / s",
                f"sum by (site) (rate(minieyes_publish_failures_total{{{SITE}}}[5m]))",
                "{{site}}",
                12,
                4,
            ),
        ],
        [variable("site", "label_values(minieyes_camera_up, site)")],
    )


def detector() -> dict:
    return dashboard(
        "minieyes-detector",
        "MiniEyes / Detector",
        [
            panel(
                1,
                "Camera up",
                f"minieyes_camera_up{{{CAM}}}",
                "{{site}} {{camera}}",
                0,
                0,
                unit="bool",
            ),
            panel(
                2,
                "Frames per second",
                f"sum by (site, camera) (rate(minieyes_frames_total{{{CAM}}}[2m]))",
                "{{site}} {{camera}}",
                12,
                0,
                unit="fps",
            ),
            panel(
                3,
                "Inference latency p95",
                f"histogram_quantile(0.95, sum by (site, le) (rate(minieyes_inference_seconds_bucket{{{SITE}}}[5m])))",
                "{{site}}",
                0,
                8,
                unit="s",
            ),
            panel(
                4,
                "Frames dropped / s (consumer slower than camera)",
                f"sum by (site, camera) (rate(minieyes_frames_dropped_total{{{CAM}}}[2m]))",
                "{{site}} {{camera}}",
                12,
                8,
            ),
            panel(
                5,
                "People detected / s",
                f"sum by (site, camera) (rate(minieyes_detections_total{{{CAM}}}[2m]))",
                "{{site}} {{camera}}",
                0,
                16,
            ),
            panel(
                6,
                "Intrusions by zone (1h)",
                f"sum by (site, camera, zone) (increase(minieyes_events_total{{{CAM}}}[1h]))",
                "{{site}} {{camera}} {{zone}}",
                12,
                16,
                kind="bargauge",
            ),
        ],
        [
            variable("site", "label_values(minieyes_camera_up, site)"),
            variable("camera", 'label_values(minieyes_camera_up{site=~"$site"}, camera)'),
        ],
    )


def event_api() -> dict:
    return dashboard(
        "minieyes-event-api",
        "MiniEyes / Event API",
        [
            panel(
                1,
                "Requests / s by route and status",
                "sum by (route, status) (rate(minieyes_api_requests_total[5m]))",
                "{{route}} {{status}}",
                0,
                0,
            ),
            panel(
                2,
                "Latency p95 by route",
                "histogram_quantile(0.95, sum by (route, le) (rate(minieyes_api_request_seconds_bucket[5m])))",
                "{{route}}",
                12,
                0,
                unit="s",
            ),
            panel(
                3,
                "5xx ratio",
                'sum(rate(minieyes_api_requests_total{status=~"5.."}[5m])) '
                "/ clamp_min(sum(rate(minieyes_api_requests_total[5m])), 0.000001)",
                "5xx",
                0,
                8,
                unit="percentunit",
            ),
            panel(
                4,
                "Rejected keys (401/403) / s",
                'sum by (status) (rate(minieyes_api_requests_total{status=~"401|403"}[5m]))',
                "{{status}}",
                12,
                8,
            ),
        ],
        [],
    )


def render() -> dict[str, str]:
    return {
        f"{d['uid']}.json": json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        for d in (fleet(), detector(), event_api())
    }


def main() -> int:
    stale = []
    for name, text in render().items():
        path = OUT / name
        if "--check" in sys.argv:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
    if stale:
        print("out of date (run build_dashboards.py):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
