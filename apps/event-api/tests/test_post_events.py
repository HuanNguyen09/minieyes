import pytest
from conftest import KEY_SITE_01, count_rows, valid_event

SITE_01 = {"X-API-Key": KEY_SITE_01}


def test_missing_api_key_returns_401_and_stores_nothing(client, engine):
    response = client.post("/events", json=valid_event())

    assert response.status_code == 401
    assert count_rows(engine) == 0


def test_unknown_api_key_returns_401_and_stores_nothing(client, engine):
    response = client.post("/events", json=valid_event(), headers={"X-API-Key": "nope"})

    assert response.status_code == 401
    assert count_rows(engine) == 0


def test_valid_event_returns_201_and_is_stored(client, engine):
    response = client.post("/events", json=valid_event(), headers=SITE_01)

    assert response.status_code == 201
    assert response.json() == {**valid_event(), "received_at": "2026-11-03T08:15:05Z"}
    assert count_rows(engine) == 1


def test_event_for_another_site_returns_403_and_stores_nothing(client, engine):
    response = client.post("/events", json=valid_event(site="site-02"), headers=SITE_01)

    assert response.status_code == 403
    assert count_rows(engine) == 0


def test_same_event_id_again_returns_200_with_the_first_copy_and_no_duplicate(client, engine, now):
    first = client.post("/events", json=valid_event(), headers=SITE_01)
    now.advance(30)
    again = client.post("/events", json=valid_event(confidence=0.5), headers=SITE_01)

    assert again.status_code == 200
    assert again.json() == first.json()
    assert count_rows(engine) == 1


@pytest.mark.parametrize("field", list(valid_event()))
def test_missing_field_returns_422(client, engine, field):
    event = valid_event()
    del event[field]

    response = client.post("/events", json=event, headers=SITE_01)

    assert response.status_code == 422
    assert count_rows(engine) == 0


@pytest.mark.parametrize("confidence", [-0.01, 1.01, "high"])
def test_confidence_outside_0_1_returns_422(client, engine, confidence):
    response = client.post("/events", json=valid_event(confidence=confidence), headers=SITE_01)

    assert response.status_code == 422
    assert count_rows(engine) == 0


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_confidence_bounds_are_inclusive(client, confidence):
    response = client.post("/events", json=valid_event(confidence=confidence), headers=SITE_01)

    assert response.status_code == 201


@pytest.mark.parametrize(
    "bbox",
    [
        [1, 2, 3],
        [1, 2, 3, 4, 5],
        [1, 2, "x", 4],
        [10, 2, 10, 4],  # x1 == x2
        [10, 2, 5, 4],  # x1 > x2
        [1, 4, 3, 4],  # y1 == y2
        [1, 9, 3, 4],  # y1 > y2
    ],
)
def test_bad_bbox_returns_422(client, engine, bbox):
    response = client.post("/events", json=valid_event(bbox=bbox), headers=SITE_01)

    assert response.status_code == 422
    assert count_rows(engine) == 0


def test_occurred_at_without_timezone_returns_422(client, engine):
    event = valid_event(occurred_at="2026-11-03T08:15:02")

    response = client.post("/events", json=event, headers=SITE_01)

    assert response.status_code == 422
    assert count_rows(engine) == 0


def test_occurred_at_with_offset_is_stored_as_utc(client):
    event = valid_event(occurred_at="2026-11-03T15:15:02+07:00")

    response = client.post("/events", json=event, headers=SITE_01)

    assert response.json()["occurred_at"] == "2026-11-03T08:15:02Z"


def test_missing_key_wins_over_invalid_body(client):
    response = client.post("/events", json={"site": "site-01"})

    assert response.status_code == 401
