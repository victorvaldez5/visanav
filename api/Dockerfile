ARG PYTHON_VERSION=3.13-slim

# Base layer with system deps shared by all stages
FROM python:${PYTHON_VERSION} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq-dev gcc \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Builder stage: install Python deps into an in-project virtualenv (.venv)
FROM base AS builder
# Use Poetry just to resolve/install into a local venv for reproducible builds
RUN pip install --no-cache-dir poetry
# Only copy dependency manifests first for better layer caching
COPY ./api/pyproject.toml ./api/poetry.lock /app/
# Install prod-only deps into a local venv inside /app, honoring the lock file
# so builds are reproducible (pins opentelemetry-api 1.36.0 that pydantic-ai needs)
RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-root --no-interaction --no-ansi
# Now copy the application code
COPY ./api /app

# Development stage: includes autoreload and dev server
FROM base AS development
# Bring in the virtualenv created by builder'
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app/ /app/
RUN chmod +x ./entrypoint.sh || true
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
# Uvicorn auto-reload for DX
CMD ["python", "-m", "uvicorn", "api_project.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage: minimal runtime image
FROM base AS production
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
RUN chmod +x ./entrypoint.sh || true
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
# Gunicorn with Uvicorn worker for ASGI.
# Shell form so ${PORT} expands: Railway injects a dynamic $PORT to bind; Fly and
# local compose set PORT=8000 (or fall back to the default here). `exec` keeps
# gunicorn as PID 1's child so it receives SIGTERM for graceful shutdown.
CMD ["sh", "-c", "exec gunicorn --bind :${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --worker-class uvicorn.workers.UvicornWorker api_project.asgi"]
