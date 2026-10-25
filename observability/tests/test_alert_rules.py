"""Structural checks on the alert rules that promtool cannot express."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
OBS = REPO / "observability"
RUNBOOK_PREFIX = "https://github.com/HuanNguyen09/minieyes/blob/main/"
SEVERITIES = {"critical", "warning"}


def _rules() -> list[dict]:
    rules = []
    for path in sorted((OBS / "alerts").glob("*.rules.yaml")):
        for group in yaml.safe_load(path.read_text(encoding="utf-8"))["groups"]:
            rules.extend(r for r in group["rules"] if "alert" in r)
    return rules


def _prd_alerts() -> set[str]:
    prd = (REPO / "PRD.md").read_text(encoding="utf-8")
    section = prd.split("### 7.3 Alert contract", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| `(\w+)` \|", section, flags=re.MULTILINE))


def test_alert_names_match_prd_contract():
    assert {r["alert"] for r in _rules()} == _prd_alerts()


def test_every_alert_has_severity_and_annotations():
    for rule in _rules():
        assert rule["labels"]["severity"] in SEVERITIES, rule["alert"]
        for key in ("summary", "description", "runbook_url"):
            assert rule["annotations"].get(key), (rule["alert"], key)


def test_every_runbook_url_points_at_an_existing_runbook():
    for rule in _rules():
        url = rule["annotations"]["runbook_url"]
        assert url.startswith(RUNBOOK_PREFIX + "docs/runbooks/"), url
        assert (REPO / url.removeprefix(RUNBOOK_PREFIX)).is_file(), url


def test_prometheusrule_manifest_is_up_to_date():
    script = OBS / "scripts" / "build_prometheusrule.py"
    result = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
