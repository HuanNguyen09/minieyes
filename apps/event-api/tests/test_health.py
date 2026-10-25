import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from minieyes_api.app import create_app


def unreachable_engine():
    """An engine whose every connection attempt fails, like a database that is down."""

    def refuse():
        raise OSError("connection refused")

    return create_engine("sqlite://", creator=refuse)


@pytest.fixture
def client_without_db(settings, registry):
    with TestClient(create_app(settings, unreachable_engine(), registry=registry)) as client:
        yield client


def test_healthz_answers_without_touching_the_database(client_without_db):
    response = client_without_db.get("/healthz")

    assert response.status_code == 200


def test_readyz_is_503_while_the_database_is_unreachable(client_without_db):
    response = client_without_db.get("/readyz")

    assert response.status_code == 503


def test_readyz_is_200_when_the_database_answers(client):
    response = client.get("/readyz")

    assert response.status_code == 200


def test_metrics_count_requests_and_latency_by_route_template_and_status(client, registry):
    client.get("/events", headers={"X-API-Key": "wrong"})  # 401
    client.get("/events?camera=cam1", headers={"X-API-Key": "wrong"})  # same route template
    client.get("/healthz")

    body = client.get("/metrics").text

    assert 'minieyes_api_requests_total{method="GET",route="/events",status="401"} 2.0' in body
    assert 'minieyes_api_requests_total{method="GET",route="/healthz",status="200"} 1.0' in body
    assert 'minieyes_api_request_seconds_count{method="GET",route="/events"} 2.0' in body
    assert "camera=cam1" not in body
