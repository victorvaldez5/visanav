# The scheduled-ingestion image: the API code plus the S3 client, running
# `manage.py refresh_corpus` and nothing else (no web server, no entrypoint.sh).
#
# It is a separate file, not another stage of api/Dockerfile, because Railway
# builds a Dockerfile's last stage and that one must stay the web image. Keep the
# base and builder steps here in line with api/Dockerfile. Build from the repo
# root:  docker build -f api/ingest.Dockerfile .
ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libpq-dev gcc \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /workspace
COPY ./pyproject.toml ./uv.lock ./.python-version ./
COPY ./api/pyproject.toml ./api/
COPY ./scrapers/uscis_scraper/pyproject.toml ./scrapers/uscis_scraper/
COPY ./data/scripts/pyproject.toml ./data/scripts/
# The api's locked deps plus its `ingest` group (boto3), which the web image omits.
RUN uv sync --locked --package api --no-dev --group ingest --no-install-workspace

FROM base AS ingest
COPY --from=builder /opt/venv /opt/venv
COPY ./api /app
# The curated corpus, read by `refresh_corpus` from KNOWLEDGE_DATA_DIR
# (set it to /app/data/countries on the service).
COPY ./data /app/data
ENV KNOWLEDGE_DATA_DIR=/app/data/countries
CMD ["python", "manage.py", "refresh_corpus"]
