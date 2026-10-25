"""ASGI entrypoint: `uvicorn minieyes_api.main:app`. Settings come from MINIEYES_* env vars;
run `python -m minieyes_api.migrate` before starting a new version."""

from fastapi import FastAPI
from prometheus_client import REGISTRY, CollectorRegistry
from sqlalchemy import create_engine

from minieyes_api.app import create_app
from minieyes_api.settings import Settings


def build(registry: CollectorRegistry = REGISTRY) -> FastAPI:
    settings = Settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return create_app(settings, engine, registry=registry)


app = build()
