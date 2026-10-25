"""FastAPI application factory: every dependency is passed in so tests can inject fakes."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from prometheus_client import CollectorRegistry
from pydantic import AwareDatetime
from sqlalchemy import Engine

from minieyes_api import cursor as cursors
from minieyes_api.auth import KeyRing
from minieyes_api.repository import EventFilter, EventRepository
from minieyes_api.schemas import EventIn, EventOut, EventPage
from minieyes_api.settings import Settings

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def create_app(
    settings: Settings,
    engine: Engine,
    registry: CollectorRegistry | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    app = FastAPI(title="MiniEyes Event API")
    keys = KeyRing(settings.api_keys)
    repo = EventRepository(engine)

    def caller_site(x_api_key: Annotated[str | None, Header()] = None) -> str:
        site = keys.site_for(x_api_key)
        if site is None:
            raise HTTPException(status_code=401, detail="missing or unknown API key")
        return site

    Site = Annotated[str, Depends(caller_site)]

    @app.post("/events", status_code=201)
    def post_event(event: EventIn, site: Site, response: Response) -> EventOut:
        if event.site != site:
            raise HTTPException(status_code=403, detail="API key is not valid for this site")
        stored, created = repo.add(event, received_at=now())
        if not created:
            response.status_code = 200
        return stored

    @app.get("/events")
    def get_events(
        site: Site,
        site_filter: Annotated[str | None, Query(alias="site")] = None,
        camera: str | None = None,
        zone: str | None = None,
        since: Annotated[AwareDatetime | None, Query(alias="from")] = None,
        until: Annotated[AwareDatetime | None, Query(alias="to")] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> EventPage:
        """Events of the caller's site, newest first. Pass `next` back as `cursor`, with the
        same filters, to get the following (older) page."""
        if site_filter is not None and site_filter != site:
            raise HTTPException(status_code=403, detail="API key is not valid for this site")
        try:
            after = None if cursor is None else cursors.decode(cursor)
        except cursors.InvalidCursor:
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("query", "cursor"), "msg": "invalid cursor"}]
            ) from None
        filters = EventFilter(site=site, camera=camera, zone=zone, since=since, until=until)
        items, last = repo.page(filters, limit=limit, after=after)
        return EventPage(items=items, next=None if last is None else cursors.encode(last))

    return app
