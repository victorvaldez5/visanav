# VisaNav

Immigration RAG AI Chatbot

A free, open tool that helps immigrants understand their options and find trustworthy help. It answers
immigration questions in plain language and points people to official government sources and to free or
low-cost nonprofit and pro-bono legal help — including DOJ-recognized organizations — while warning about
common immigration scams.

## Features

- Weekly scheduled (and on-demand) USCIS crawl — forms, the INA, and the Policy Manual — to Cloudflare R2
- Lightweight, containerized services
- Extendable Python codebase
- pgvector + Voyage embeddings for the RAG vector store
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
- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you)
- [just](https://just.systems/) (task runner; `brew install just uv` on macOS)
- Node.js + npm (frontend)
- Docker & Docker Compose

---

## Getting Started

1. Clone the repository
   ```bash
   git clone https://github.com/victorvaldez5/visanav.git
   cd visanav
   ```

2. Install everything
   ```bash
   cp config/.env.example config/.env   # then fill in the secrets marked "CHANGE ME"
   just setup                           # uv sync --all-packages + npm install
   ```
   The Python services (`api`, the scraper, the data tooling) share one
   [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): a
   single `uv.lock` and one `.venv` at the repo root. Run `just` to see every task.

---

## Configuration

All environment variables live in one place: **`config/.env`**.

```bash
cp config/.env.example config/.env   # then fill in the secrets marked "CHANGE ME"
```

`config/.env.example` is committed and documents every variable (Django, Postgres,
LLM keys, Voyage embeddings, email, scraper). `config/.env` is gitignored and is read by:

- `docker-compose.yml` — all services, via `env_file`
- the Django API — `api/api_project/base.py`
- the Scrapy scraper — `scrapers/uscis_scraper/uscis_scraper/settings.py`
(The corpus ingest command, `api/manage.py ingest`, reads env via Django settings.)

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
- **Tests**: the `scraper` job in `.github/workflows/ci.yml` runs the scraper's pytest suite on
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
  --set 'VOYAGE_API_KEY=<key>' \
  --set 'CONVERSATION_ENCRYPTION_KEYS=<fernet-key>'
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

**Migrations run as a Railway pre-deploy command** (`preDeployCommand` in
[`railway.json`](railway.json)): once per release, before the new version takes
traffic, and a failing migration aborts the deploy so the old version keeps
serving. Set `SKIP_MIGRATE_ON_START=1` on the API service so the container
doesn't migrate a second time on every cold start. If the variable is unset it
is harmless (migrate is idempotent), just redundant. `api/entrypoint.sh` still
runs `collectstatic` on every start, and still migrates on boot locally.

Before a `develop` → `main` release, work through [`docs/RELEASING.md`](docs/RELEASING.md).

---

## Data retention & encryption

Conversation content is the app's most sensitive data, so the store keeps little
and holds none of it in plaintext.

- **Encrypted at rest.** `Message.parts` is Fernet-encrypted (`core/encryption.py`).
  Set `CONVERSATION_ENCRYPTION_KEYS` in prod; dev/CI derive a throwaway key.
- **Retention.** Each conversation has an `expires_at`, refreshed per turn:
  `CONVERSATION_ANON_RETENTION_DAYS` (7) / `CONVERSATION_USER_RETENTION_DAYS` (30),
  or kept when the user opts in (`Profile.retain_history`). `0` disables it.
- **Deletion.** `python manage.py purge_expired_conversations` (`--dry-run` to
  preview); `railway.cron.json` runs it daily on Railway.
- **Legal hold.** The purge skips `legal_hold=True` — set it (admin at `/nimda/`)
  before deleting data you're on notice to preserve.

---

## Production Checklist

- [ ] `DJANGO_SETTINGS_MODULE=api_project.prod`, and `DJANGO_SECRET_KEY` /
      `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `POSTGRES_*` all set (prod
      refuses to boot otherwise).
- [ ] `CONVERSATION_ENCRYPTION_KEYS` set to a real, backed-up Fernet key — losing
      it makes every stored conversation unreadable.
- [ ] `purge_expired_conversations` scheduled — the `railway.cron.json` service
      is deployed, has its env vars set, and a dry-run was confirmed in its logs.
- [ ] Retention windows (`CONVERSATION_*_RETENTION_DAYS`) reviewed for the launch
      audience.
- [ ] A written, dated retention policy that matches the above (routine deletion
      is only defensible when it's consistent and documented).

---

## Contributing

Contributions are welcome, and the most valuable ones are not code: adding or
correcting per-country immigration data helps people directly. See
[CONTRIBUTING.md](CONTRIBUTING.md) to get started, and please read the
[Code of Conduct](CODE_OF_CONDUCT.md). To report a security issue, follow
[SECURITY.md](SECURITY.md) (DO NOT OPEN A PUBLIC ISSUE).

## Licensing

VisaNav is split across two licenses:

- **Code** (everything outside `data/`) is licensed under the
  [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0). Running a modified
  version as a network service requires publishing your source under the same terms.
- **Data** (the `data/` corpus of immigration knowledge and resources) is licensed
  under [Creative Commons Attribution 4.0 International](data/LICENSE) (CC-BY-4.0),
  so it can be reused widely with attribution.
