from conftest import KEY_SITE_01, sha256, valid_event
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from minieyes_api.main import build
from minieyes_api.migrate import upgrade


def test_build_wires_env_settings_to_a_working_app(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'api.db'}"
    upgrade(url)
    monkeypatch.setenv("MINIEYES_DATABASE_URL", url)
    monkeypatch.setenv("MINIEYES_API_KEYS", f'{{"site-01": "{sha256(KEY_SITE_01)}"}}')

    with TestClient(build(registry=CollectorRegistry())) as client:
        posted = client.post("/events", json=valid_event(), headers={"X-API-Key": KEY_SITE_01})
        ready = client.get("/readyz")

    assert (posted.status_code, ready.status_code) == (201, 200)
