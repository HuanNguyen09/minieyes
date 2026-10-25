import uuid

from conftest import KEY_SITE_01, KEY_SITE_02, valid_event

SITE_01 = {"X-API-Key": KEY_SITE_01}
SITE_02 = {"X-API-Key": KEY_SITE_02}


def post(client, n: int, at: str, **fields) -> str:
    """Store event number n; returns its event_id."""
    event_id = str(uuid.UUID(int=n))
    site = fields.get("site", "site-01")
    headers = SITE_01 if site == "site-01" else SITE_02
    event = valid_event(event_id=event_id, occurred_at=at, **fields)
    assert client.post("/events", json=event, headers=headers).status_code == 201
    return event_id


def ids(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [item["event_id"] for item in response.json()["items"]]


def test_returns_newest_first(client):
    a = post(client, 1, "2026-11-03T08:00:00Z")
    c = post(client, 2, "2026-11-03T10:00:00Z")
    b = post(client, 3, "2026-11-03T09:00:00Z")

    assert ids(client.get("/events", headers=SITE_01)) == [c, b, a]


def test_requires_an_api_key(client):
    assert client.get("/events").status_code == 401
    assert client.get("/events", headers={"X-API-Key": "nope"}).status_code == 401


def test_a_key_only_sees_its_own_site(client):
    mine = post(client, 1, "2026-11-03T08:00:00Z", site="site-01")
    theirs = post(client, 2, "2026-11-03T08:00:00Z", site="site-02")

    assert ids(client.get("/events", headers=SITE_01)) == [mine]
    assert ids(client.get("/events", headers=SITE_02)) == [theirs]


def test_filters_by_site(client):
    mine = post(client, 1, "2026-11-03T08:00:00Z")

    assert ids(client.get("/events", params={"site": "site-01"}, headers=SITE_01)) == [mine]


def test_filtering_by_another_site_returns_403(client):
    response = client.get("/events", params={"site": "site-02"}, headers=SITE_01)

    assert response.status_code == 403


def test_filters_by_camera_zone_and_both(client):
    cam1_lane = post(client, 1, "2026-11-03T08:00:00Z", camera="cam1", zone="lane")
    cam1_dock = post(client, 2, "2026-11-03T08:01:00Z", camera="cam1", zone="dock")
    cam2_lane = post(client, 3, "2026-11-03T08:02:00Z", camera="cam2", zone="lane")

    def query(**params):
        return ids(client.get("/events", params=params, headers=SITE_01))

    assert query(camera="cam1") == [cam1_dock, cam1_lane]
    assert query(zone="lane") == [cam2_lane, cam1_lane]
    assert query(camera="cam1", zone="lane") == [cam1_lane]
    assert query(site="site-01", camera="cam2", zone="lane") == [cam2_lane]
    assert query(camera="cam3") == []


def test_filters_by_time_range_inclusive_from_exclusive_to(client):
    at8 = post(client, 1, "2026-11-03T08:00:00Z")
    at9 = post(client, 2, "2026-11-03T09:00:00Z")
    at10 = post(client, 3, "2026-11-03T10:00:00Z")

    def query(**params):
        return ids(client.get("/events", params=params, headers=SITE_01))

    assert query(**{"from": "2026-11-03T09:00:00Z"}) == [at10, at9]
    assert query(to="2026-11-03T09:00:00Z") == [at8]
    assert query(**{"from": "2026-11-03T09:00:00Z", "to": "2026-11-03T10:00:00Z"}) == [at9]
    # 16:00 at +07:00 is 09:00 UTC
    assert query(**{"from": "2026-11-03T16:00:00+07:00"}) == [at10, at9]


def pages(client, **params) -> list[list[str]]:
    """Follow `next` cursors until the last page."""
    result = []
    cursor = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        response = client.get("/events", params=query, headers=SITE_01)
        result.append(ids(response))
        cursor = response.json()["next"]
        if cursor is None:
            return result


def test_limit_defaults_to_50(client):
    posted = [post(client, n, f"2026-11-03T08:{n:02d}:00Z") for n in range(51)]

    assert pages(client) == [posted[:0:-1], [posted[0]]]


def test_cursor_pages_walk_every_event_once_newest_first(client):
    e = [post(client, n, f"2026-11-03T08:0{n}:00Z") for n in range(5)]

    assert pages(client, limit=2) == [[e[4], e[3]], [e[2], e[1]], [e[0]]]


def test_exact_multiple_of_limit_ends_without_an_empty_page(client):
    e = [post(client, n, f"2026-11-03T08:0{n}:00Z") for n in range(4)]

    assert pages(client, limit=2) == [[e[3], e[2]], [e[1], e[0]]]


def test_pagination_is_stable_when_events_share_a_timestamp(client):
    same = [post(client, n, "2026-11-03T08:00:00Z") for n in range(5)]

    walked = [i for page in pages(client, limit=2) for i in page]

    assert walked == same[::-1]


def test_pagination_is_stable_when_newer_events_arrive_between_pages(client):
    e = [post(client, n, f"2026-11-03T08:0{n}:00Z") for n in range(4)]
    first = client.get("/events", params={"limit": 2}, headers=SITE_01)

    post(client, 99, "2026-11-03T09:00:00Z")
    second = client.get(
        "/events", params={"limit": 2, "cursor": first.json()["next"]}, headers=SITE_01
    )

    assert ids(first) == [e[3], e[2]]
    assert ids(second) == [e[1], e[0]]


def test_cursor_combines_with_filters(client):
    lane = [post(client, n, f"2026-11-03T08:0{n}:00Z", zone="lane") for n in range(3)]
    post(client, 5, "2026-11-03T08:05:00Z", zone="dock")

    assert pages(client, zone="lane", limit=2) == [[lane[2], lane[1]], [lane[0]]]


def test_limit_above_500_or_below_1_returns_422(client):
    for limit in (0, 501):
        response = client.get("/events", params={"limit": limit}, headers=SITE_01)
        assert response.status_code == 422


def test_limit_500_is_allowed(client):
    response = client.get("/events", params={"limit": 500}, headers=SITE_01)

    assert response.status_code == 200


def test_garbage_cursor_returns_422(client):
    response = client.get("/events", params={"cursor": "not-a-cursor"}, headers=SITE_01)

    assert response.status_code == 422


def test_time_range_without_timezone_returns_422(client):
    response = client.get("/events", params={"from": "2026-11-03T09:00:00"}, headers=SITE_01)

    assert response.status_code == 422
