"""Dashboards as code (#35): every panel queries a metric that exists, every dashboard can be
filtered by site, and the JSON in Git is exactly what the generator produces."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
OBS = REPO / "observability"
DASHBOARDS = sorted((OBS / "dashboards").glob("*.json"))
# exporters the platform runs next to the MiniEyes metrics
KNOWN_PREFIXES = ("up", "node_", "kube_", "nv_", "process_", "container_", "minieyes_api_")
PROMQL_FUNCS = {
    "sum",
    "rate",
    "irate",
    "increase",
    "histogram_quantile",
    "max",
    "min",
    "avg",
    "count",
    "by",
    "without",
    "on",
    "ignoring",
    "or",
    "and",
    "unless",
    "le",
    "time",
    "vector",
    "max_over_time",
    "label_replace",
    "clamp_min",
    "topk",
    "bool",
}


def prd_metrics() -> set[str]:
    prd = (REPO / "PRD.md").read_text(encoding="utf-8")
    section = prd.split("### 7.2 Metrics contract", 1)[1].split("###", 1)[0]
    return set(re.findall(r"^\| `(minieyes_\w+)` \|", section, flags=re.MULTILINE))


def metric_names(expr: str) -> set[str]:
    expr = re.sub(r"\b(by|without|on|ignoring)\s*\([^)]*\)", "", expr)  # grouping labels
    expr = re.sub(r"\{[^}]*\}", "", expr)  # label matchers
    expr = re.sub(r"\[[^\]]*\]", "", expr)  # range selectors
    expr = re.sub(r'"[^"]*"', "", expr)
    names = set(re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", expr)) - PROMQL_FUNCS
    return {n for n in names if not n.startswith("$")}


def base(name: str) -> str:
    return re.sub(r"_(bucket|count|sum)$", "", name)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expressions(dashboard: dict):
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            yield panel["title"], target["expr"]


def test_there_are_fleet_detector_and_api_dashboards():
    assert {p.stem for p in DASHBOARDS} >= {
        "minieyes-fleet",
        "minieyes-detector",
        "minieyes-event-api",
    }


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_every_query_uses_a_known_metric(path):
    contract = prd_metrics()
    for title, expr in expressions(load(path)):
        for name in metric_names(expr):
            known = base(name) in contract or name.startswith(KNOWN_PREFIXES)
            assert known, f"{path.stem} / {title}: unknown metric {name!r} in {expr!r}"


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_edge_dashboards_filter_by_site(path):
    dashboard = load(path)
    if path.stem == "minieyes-event-api":
        pytest.skip("cloud-only service")
    variables = {v["name"] for v in dashboard["templating"]["list"]}
    assert "site" in variables
    for title, expr in expressions(dashboard):
        if "minieyes_" in expr and "minieyes_api_" not in expr:
            assert 'site=~"$site"' in expr, f"{title}: {expr}"


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_dashboards_have_stable_uids_and_the_prometheus_datasource(path):
    dashboard = load(path)
    assert dashboard["uid"] == path.stem
    for panel in dashboard["panels"]:
        assert panel["datasource"] == {"type": "prometheus", "uid": "prometheus"}, panel["title"]


def test_kustomize_ships_every_dashboard_to_the_grafana_sidecar():
    kustomization = yaml.safe_load((OBS / "kustomization.yaml").read_text(encoding="utf-8"))
    generated = {g["name"]: g for g in kustomization.get("configMapGenerator", [])}
    for path in DASHBOARDS:
        cm = generated[f"dashboard-{path.stem}"]
        assert cm["files"] == [f"dashboards/{path.name}"]
        assert cm["options"]["labels"]["grafana_dashboard"] == "1"


def test_committed_json_matches_the_generator():
    script = OBS / "scripts" / "build_dashboards.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
