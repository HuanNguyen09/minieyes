"""HTTP metrics labelled by route template, so query strings and ids never create new series."""

import time

from fastapi import FastAPI, Request
from prometheus_client import CollectorRegistry, Counter, Histogram


def instrument(app: FastAPI, registry: CollectorRegistry) -> None:
    requests = Counter(
        "minieyes_api_requests_total",
        "HTTP requests by route template and status",
        ["method", "route", "status"],
        registry=registry,
    )
    latency = Histogram(
        "minieyes_api_request_seconds",
        "HTTP request latency by route template",
        ["method", "route"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        registry=registry,
    )

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        latency.labels(request.method, template).observe(time.perf_counter() - start)
        requests.labels(request.method, template, str(response.status_code)).inc()
        return response
