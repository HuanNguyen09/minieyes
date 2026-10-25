# Build from the repo root: docker build -f apps/detector/Dockerfile .
FROM ghcr.io/astral-sh/uv:0.12.10 AS uv

FROM python:3.12.14-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src
# dependencies first, so source edits do not invalidate this layer
COPY pyproject.toml uv.lock ./
COPY apps/detector/pyproject.toml apps/detector/pyproject.toml
COPY apps/event-api/pyproject.toml apps/event-api/pyproject.toml
RUN uv sync --frozen --no-dev --package minieyes-detector --no-install-workspace
COPY apps/detector/src apps/detector/src
RUN uv sync --frozen --no-dev --package minieyes-detector --no-editable

FROM python:3.12.14-slim-trixie
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin minieyes
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8080
# importing cv2 and tritonclient takes several seconds on a cold start
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
ENTRYPOINT ["python", "-m", "minieyes_detector"]
