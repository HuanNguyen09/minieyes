"""Alertmanager grouping and inhibition (issue #32).

Routing is covered by observability/alertmanager/test.sh (amtool). amtool does not
show group_by or evaluate inhibit rules, so this module checks grouping statically
and, when an `alertmanager` binary is on PATH, against a real Alertmanager.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

CONFIG = Path(__file__).resolve().parents[1] / "alertmanager" / "alertmanager.yaml"


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- static


def test_alerts_are_grouped_by_alertname_and_site():
    route = _config()["route"]
    assert route["group_by"] == ["alertname", "site"]
    # child routes inherit unless they override
    for child in route["routes"]:
        assert child.get("group_by", route["group_by"]) == ["alertname", "site"]


def test_bot_token_is_read_from_a_mounted_secret():
    text = CONFIG.read_text(encoding="utf-8")
    for receiver in _config()["receivers"]:
        for tg in receiver.get("telegram_configs", []):
            assert "bot_token" not in tg
            assert tg["bot_token_file"].startswith("/etc/alertmanager/secrets/")
    assert "bot_token:" not in text


# ------------------------------------------------------------------ live

ALERTMANAGER = shutil.which("alertmanager")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read() or b"null")


def _post(url: str, payload) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5):
        pass


@pytest.fixture(scope="module")
def alertmanager(tmp_path_factory) -> Iterator[str]:
    if ALERTMANAGER is None:
        pytest.skip("alertmanager binary not on PATH")
    tmp = tmp_path_factory.mktemp("am")
    token = tmp / "bot-token"
    token.write_text("000000:fake-token-for-tests")
    config = _config()
    for receiver in config["receivers"]:
        for tg in receiver.get("telegram_configs", []):
            tg["bot_token_file"] = str(token)
            tg["api_url"] = "http://127.0.0.1:9"  # never reach the real Telegram API
    cfg = tmp / "alertmanager.yaml"
    cfg.write_text(yaml.safe_dump(config), encoding="utf-8")
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            ALERTMANAGER,
            f"--config.file={cfg}",
            f"--storage.path={tmp / 'data'}",
            f"--web.listen-address=127.0.0.1:{port}",
            "--cluster.listen-address=",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(f"{base}/-/ready", timeout=1)
                break
            except OSError:
                if time.monotonic() > deadline or proc.poll() is not None:
                    pytest.fail("alertmanager did not become ready")
                time.sleep(0.3)
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _alert(alertname: str, severity: str, site: str, **labels: str) -> dict:
    return {"labels": {"alertname": alertname, "severity": severity, "site": site, **labels}}


@pytest.fixture(scope="module")
def alerts(alertmanager: str) -> dict[tuple[str, str, str], dict]:
    _post(
        f"{alertmanager}/api/v2/alerts",
        [
            _alert("EdgeSiteSilent", "critical", "site-01"),
            _alert("CameraDown", "critical", "site-01", camera="cam1"),
            _alert("LowFPS", "warning", "site-01", camera="cam2"),
            _alert("CameraDown", "critical", "site-02", camera="cam1"),
            _alert("CameraDown", "critical", "site-02", camera="cam2"),
            _alert("DiskFull", "critical", "site-03"),
            _alert("DiskFull", "warning", "site-03"),
        ],
    )
    got = _get(f"{alertmanager}/api/v2/alerts")
    return {
        (a["labels"]["alertname"], a["labels"]["site"], a["labels"].get("camera", a["labels"]["severity"])): a
        for a in got
    }


def _inhibited(alert: dict) -> bool:
    return alert["status"]["state"] == "suppressed" and bool(alert["status"]["inhibitedBy"])


def test_edge_site_silent_inhibits_other_alerts_of_the_same_site(alerts):
    assert _inhibited(alerts[("CameraDown", "site-01", "cam1")])
    assert _inhibited(alerts[("LowFPS", "site-01", "cam2")])
    assert not _inhibited(alerts[("EdgeSiteSilent", "site-01", "critical")])


def test_edge_site_silent_does_not_inhibit_other_sites(alerts):
    assert not _inhibited(alerts[("CameraDown", "site-02", "cam1")])


def test_critical_inhibits_warning_of_the_same_alert_and_site(alerts):
    assert _inhibited(alerts[("DiskFull", "site-03", "warning")])
    assert not _inhibited(alerts[("DiskFull", "site-03", "critical")])


def test_live_groups_are_keyed_by_alertname_and_site(alertmanager, alerts):
    groups = _get(f"{alertmanager}/api/v2/alerts/groups")
    keys = {tuple(sorted(g["labels"].items())) for g in groups}
    assert (("alertname", "CameraDown"), ("site", "site-02")) in keys
    site02 = next(
        g for g in groups if g["labels"] == {"alertname": "CameraDown", "site": "site-02"}
    )
    assert len(site02["alerts"]) == 2  # two cameras, one Telegram message
