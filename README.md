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

## Deploying the API (Railway)

The API is deployed to **Railway** as a Dockerfile service plus a managed
Postgres. Redis is not needed — the app uses Django's in-process `LocMemCache`.
Build/deploy config lives in [`railway.json`](railway.json); it builds the
`production` stage of [`api/Dockerfile`](api/Dockerfile) (the final stage) from
the **repo root** as the build context.

> Gunicorn binds `${PORT}` (Railway injects a dynamic port). Locally and under
> compose, `PORT` defaults to `8000`.

### One-time setup

```bash
railway init -n visanav              # create + link the project
railway add --database postgres      # provision managed Postgres (named "Postgres", pgvector-ready)
railway add --service visanav-api    # create the API service (empty for now)
```

### Environment variables (set on the API service)

Set these **before the first `railway up`** — `prod.py` refuses to boot without
`DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, and the `POSTGRES_*` vars. Postgres is wired
from the Postgres service via reference variables, so nothing is copy-pasted, and
`RAILWAY_PUBLIC_DOMAIN` auto-fills the generated `*.up.railway.app` host so
`ALLOWED_HOSTS` needs no manual edit.

```bash
railway variables --service visanav-api \
  --set 'DJANGO_SETTINGS_MODULE=api_project.prod' \
  --set 'DJANGO_SECRET_KEY=<run: python -c "import secrets;print(secrets.token_urlsafe(64))">' \
  --set 'ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}}' \
  --set 'CSRF_TRUSTED_ORIGINS=https://<frontend-domain>,https://${{RAILWAY_PUBLIC_DOMAIN}}' \
  --set 'FRONTEND_URL=https://<frontend-domain>' \
  --set 'SECURE_SSL_REDIRECT=true' \
  --set 'POSTGRES_DB=${{Postgres.PGDATABASE}}' \
  --set 'POSTGRES_USER=${{Postgres.PGUSER}}' \
  --set 'POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}' \
  --set 'POSTGRES_HOST=${{Postgres.PGHOST}}' \
  --set 'POSTGRES_PORT=${{Postgres.PGPORT}}' \
  --set 'POSTGRES_SSLMODE=prefer' \
  --set 'ANTHROPIC_API_KEY=<key>' \
  --set 'PINECONE_API_KEY=<key>' \
  --set 'PINECONE_INDEX_HOST=<serverless-host>' \
  --set 'PINECONE_NAMESPACE=us'
```

> **Gotcha:** `prod.py` reuses `CSRF_TRUSTED_ORIGINS` as `CORS_ALLOWED_ORIGINS`,
> so it **must** include the frontend origin (with scheme) or the chat UI's
> cross-origin calls to the API will be blocked. `POSTGRES_SSLMODE=prefer` is
> used because the Postgres private endpoint (`*.railway.internal`) is reached
> over Railway's isolated network; `prefer` negotiates TLS when available and
> won't fail if it isn't (the prod default of `require` would).

### Deploy

```bash
railway up --service visanav-api      # build + deploy from the repo root
railway domain --service visanav-api  # generate the public HTTPS domain
```

> Prefer auto-deploys? Connect the GitHub repo to the API service in the Railway
> dashboard instead of `railway up`; it reads `railway.json` and redeploys on push.

`api/entrypoint.sh` runs `migrate` and `collectstatic` on container start, so
the schema and WhiteNoise static manifest are applied automatically. (Optional
hardening: move `migrate` to a Railway *pre-deploy command* so it runs once per
release instead of on every cold start under scale-to-zero.)

---

## Data retention & encryption

Conversations hold people's immigration questions — the most sensitive data in
the app — so the store is built to keep as little as possible, for as short as
possible, and never in plaintext.

**Encryption at rest.** `Message.parts` (the raw conversation content) is stored
Fernet-encrypted via `core/encryption.py` + `core.fields.EncryptedJSONField`; the
database column holds ciphertext. This is *defence-in-depth for the store* — a DB
dump, stolen backup, or leaked replica yields ciphertext. It is **not**
end-to-end encryption: the API decrypts each turn to run the model, and whoever
holds the key (including us, under legal process) can read stored chats. Set a
real key in prod — `api_project.prod` refuses to boot without an explicit
`CONVERSATION_ENCRYPTION_KEYS` (in dev/CI a throwaway key is derived from the dev
`SECRET_KEY`, so no key material is committed):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → set as CONVERSATION_ENCRYPTION_KEYS on the API service
```

Rotate by prepending a new key (`new,old`) and re-saving rows; both are tried on
decrypt.

**Retention.** Each conversation carries an `expires_at`, set on creation and
refreshed on every turn (so an active chat stays alive and an abandoned one ages
out). Anonymous chats use `CONVERSATION_ANON_RETENTION_DAYS` (default 7);
signed-in chats use `CONVERSATION_USER_RETENTION_DAYS` (default 30) **unless** the
user opts into keeping history (`Profile.retain_history`), which sets
`expires_at = NULL`. A window of `0` disables auto-expiry for that class.

Deletion is enforced by a management command — schedule it (Railway cron service
or a scheduled GitHub Action):

```bash
python manage.py purge_expired_conversations            # delete expired
python manage.py purge_expired_conversations --dry-run  # report only
```

**Legal hold.** The purge command **never** deletes a conversation with
`legal_hold=True`. Routine, policy-driven deletion is defensible; deleting data
you're already on notice to preserve is not. When a subpoena or litigation-hold
demand arrives, set the hold *before* the next purge — the "Place legal hold"
admin action (at `/nimda/`) flips it for selected conversations; lift it when the
duty ends. (The hold procedure is the one piece here genuinely worth confirming
with counsel.)

---

## Production Checklist

- [ ] `DJANGO_SETTINGS_MODULE=api_project.prod`, and `DJANGO_SECRET_KEY` /
      `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `POSTGRES_*` all set (prod
      refuses to boot otherwise).
- [ ] `CONVERSATION_ENCRYPTION_KEYS` set to a real, backed-up Fernet key — losing
      it makes every stored conversation unreadable.
- [ ] `purge_expired_conversations` scheduled (Railway cron or GitHub Action) and
      confirmed running.
- [ ] Retention windows (`CONVERSATION_*_RETENTION_DAYS`) reviewed for the launch
      audience.
- [ ] A written, dated retention policy that matches the above (routine deletion
      is only defensible when it's consistent and documented).
