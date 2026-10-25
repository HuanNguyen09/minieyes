"""FastAPI application factory: every dependency is passed in so tests can inject fakes."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from prometheus_client import CollectorRegistry
from sqlalchemy import Engine

from minieyes_api.auth import KeyRing
from minieyes_api.repository import EventRepository
from minieyes_api.schemas import EventIn, EventOut
from minieyes_api.settings import Settings


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

    return app
