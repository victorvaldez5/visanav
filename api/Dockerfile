ARG PYTHON_VERSION=3.13-slim

# Base layer with system deps shared by all stages
FROM python:${PYTHON_VERSION} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq-dev gcc \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Builder stage: install the api's locked deps (only the api workspace member,
# never the scraper's Scrapy/boto3) into a venv at /opt/venv. It lives outside
# /app so the dev bind mount (./api:/app) can't shadow it.
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Only the workspace manifests + lock first, for layer caching. uv reads every
# member's pyproject.toml to validate the workspace, even the ones not installed.
WORKDIR /workspace
COPY ./pyproject.toml ./uv.lock ./.python-version ./
COPY ./api/pyproject.toml ./api/
COPY ./scrapers/uscis_scraper/pyproject.toml ./scrapers/uscis_scraper/
COPY ./data/scripts/pyproject.toml ./data/scripts/
# --locked fails the build if uv.lock is stale rather than silently re-resolving.
RUN uv sync --locked --package api --no-dev --no-install-workspace
WORKDIR /app
# Now copy the application code
COPY ./api /app
# Bring in the curated resource corpus next to the app so the `load_resources`
# management command can find data/ inside the container (see SEED_DIRECTORY in
# entrypoint.sh). Tiny (~100K) and resolved via repo_data_dir()'s upward search.
COPY ./data /app/data

# Development stage: includes autoreload and dev server
FROM base AS development
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/ /app/
RUN chmod +x ./entrypoint.sh || true
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
# Uvicorn auto-reload for DX
CMD ["python", "-m", "uvicorn", "api_project.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage: minimal runtime image
FROM base AS production
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
RUN chmod +x ./entrypoint.sh || true
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
# Gunicorn with Uvicorn worker for ASGI.
# Shell form so ${PORT} expands: Railway injects a dynamic $PORT to bind; Fly and
# local compose set PORT=8000 (or fall back to the default here). `exec` keeps
# gunicorn as PID 1's child so it receives SIGTERM for graceful shutdown.
CMD ["sh", "-c", "exec gunicorn --bind :${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --worker-class uvicorn.workers.UvicornWorker api_project.asgi"]
