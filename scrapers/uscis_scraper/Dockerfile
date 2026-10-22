###############################################################################
# Built with the repo root as context (docker-compose), so the uv workspace
# manifests are reachable. Installs only the uscis-scraper workspace member's
# locked deps (never the api's Django stack) into /opt/venv, outside /app so the
# dev bind mount (./scrapers/uscis_scraper:/app) can't shadow it.
###############################################################################
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

###############################################################################
# 1) BUILDER: install the locked wheels (no resolution happens here)
###############################################################################
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# uv reads every member's pyproject.toml to validate the workspace, even the
# ones not installed.
WORKDIR /workspace
COPY ./pyproject.toml ./uv.lock ./.python-version ./
COPY ./api/pyproject.toml ./api/
COPY ./scrapers/uscis_scraper/pyproject.toml ./scrapers/uscis_scraper/
COPY ./data/scripts/pyproject.toml ./data/scripts/
# --locked fails the build if uv.lock is stale rather than silently re-resolving.
RUN uv sync --locked --package uscis-scraper --no-dev --no-install-workspace

###############################################################################
# 2) DEVELOPMENT: code comes from the compose bind mount
###############################################################################
FROM base AS development
COPY --from=builder /opt/venv /opt/venv
CMD ["scrapy", "crawl", "uscis"]

###############################################################################
# 3) PRODUCTION: venv + the scraper code baked in
###############################################################################
FROM base AS production
# Production crawls write to R2. settings.py defaults LOCAL_TEST to true, so
# without this a service missing the variable would crawl into the container's
# ephemeral disk and still exit 0. (Dev and compose keep the safe local default.)
ENV LOCAL_TEST=false
COPY --from=builder /opt/venv /opt/venv
COPY scrapers/uscis_scraper/ .
CMD ["scrapy", "crawl", "uscis"]
