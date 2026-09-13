# Project Raul Overview

Immigration RAG AI Chatbot

A chatbot that helps immigrants find the right immigration status and services. Helping people apply for immigration,
find immigration status, and find immigration services. Connecting with the right attorneys and lawyers.
Allowing for secure communication and document sharing with your attorneys.

## Features

- Weekly scheduled (and on-demand) USCIS crawl — forms, the INA, and the Policy Manual — to Cloudflare R2
- Lightweight, containerized services
- Extendable Python codebase
- Pinecone integration for vector database
- vue frontend chat interface
- django backend api server
- docker-compose for local development
- Pydnatic-ai for AI Agent based chatbot

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Getting Started](#getting-started)
3. [Configuration](#configuration)
4. [Development Workflow](#development-workflow)
5. [Running with Docker Compose](#running-with-docker-compose)
6. [Cleaning Up](#cleaning-up)

---

## Prerequisites

- Git (to clone the repo)
- Python 3.13.5
- [pip](https://pip.pypa.io/)
- Docker & Docker Compose

---

## Getting Started

1. Clone the repository
   ```bash
   git clone https://github.com/victorvaldez5/visanav.git
   cd visanav
   ```

2. Create & activate a Python virtual environment
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate      # on macOS/Linux
   .\.venv\Scripts\Activate.ps1   # on Windows PowerShell
   ```

3. Install Python dependencies
   Each subdirectory is a service. Each service has its own requirements.
   to install specific project requirements, go into that service directory and run:
   ```bash
   pip install --upgrade pip
   pip install poetry
   poetry install
   ```

4. Install Frontend dependencies
   Inside the frontend directory run the following commands

```bash
npm install -D
```

---

## Configuration

All environment variables live in one place: **`config/.env`**.

```bash
cp config/.env.example config/.env   # then fill in the secrets marked "CHANGE ME"
```

`config/.env.example` is committed and documents every variable (Django, Postgres,
LLM keys, Pinecone, email, scraper). `config/.env` is gitignored and is read by:

- `docker-compose.yml` — all services, via `env_file`
- the Django API — `api/api_project/base.py`
- the Scrapy scraper — `scrapers/uscis_scraper/uscis_scraper/settings.py`
- the data ingestion script — `data/scripts/ingest.py` (for `--upsert`)

> The `${VAR}` substitutions inside `docker-compose.yml` all have built-in
> defaults, so `docker compose up` works out of the box. To feed your env file
> into those substitutions too, run `docker compose --env-file config/.env up`.

---

## Development Workflow

Use docker compose to work with the containers.

To bring up the web services (frontend, api, database) run

```bash
  docker compose up
```

to bring up the scraper run

```bash
  docker compose up uscis_scraper
```

---

## Scraper & raw data

The Scrapy `uscis` spider crawls USCIS forms, the Immigration and Nationality Act
(via uscode.house.gov), and the USCIS Policy Manual (~940 documents, ~200 MB total).

- **Storage sink** is controlled by `LOCAL_TEST` in `config/.env`:
  - `LOCAL_TEST=true` (default) writes raw HTML/PDF/JSONL under `output/` for local runs.
  - `LOCAL_TEST=false` uploads to **Cloudflare R2** (S3-compatible) under `raw/`
    (`raw/html/`, `raw/pdf/`, `raw/items/`), using `R2_BUCKET` + the `AWS_*` credentials.
- **Incremental**: a content-hash manifest (`raw/manifest.json`) lets re-runs skip
  pages whose content is unchanged, so only changed documents are re-written and
  forwarded downstream.
- **Scheduling**: `.github/workflows/scrape.yml` runs the crawl weekly (and on manual
  `workflow_dispatch`), writing to R2. It reads `R2_BUCKET`, `AWS_ENDPOINT_URL`,
  `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` from **GitHub Secrets**.
  (A Fly scheduled Machine is an alternative if you'd rather keep everything on Fly.)
- **Tests**: `.github/workflows/scraper-ci.yml` runs the scraper's pytest suite on
  every PR touching `scrapers/`.

---

## Cleaning Up

When you’re done:

- Stop & remove containers
  ```bash
  docker compose down
  ```

- Deactivate your virtual environment
  ```bash
  deactivate
  ```

- (Optional) Remove local images/volumes
  ```bash
  docker system prune
  ```

---

## Production Checklist
