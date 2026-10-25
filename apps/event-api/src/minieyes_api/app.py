"""FastAPI application factory: every dependency is passed in so tests can inject fakes."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from pydantic import AwareDatetime
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from minieyes_api import cursor as cursors
from minieyes_api.auth import KeyRing
from minieyes_api.metrics import instrument
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
    registry = registry if registry is not None else CollectorRegistry()
    instrument(app, registry)
    keys = KeyRing(settings.api_keys)
    repo = EventRepository(engine)

    def caller_site(x_api_key: Annotated[str | None, Header()] = None) -> str:
        site = keys.site_for(x_api_key)
        if site is None:
            raise HTTPException(status_code=401, detail="missing or unknown API key")
        return site

    Site = Annotated[str, Depends(caller_site)]

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness: the process answers. Never touches the database, so a database outage
        does not make Kubernetes restart every API pod."""
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/readyz")
    def readyz(response: Response) -> dict:
        """Readiness: only route traffic here while the database answers."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except (OSError, SQLAlchemyError):
            response.status_code = 503
            return {"status": "database unreachable"}
        return {"status": "ready"}

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
