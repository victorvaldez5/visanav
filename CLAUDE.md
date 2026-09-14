# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

VisaNav (a.k.a. "Project Raul" / immigration-ai) is an immigration RAG chatbot that helps
immigrants find status/services and connect with attorneys. It is a **monorepo of four
independently-deployed services** plus a shared config file:

- `api/` — Django REST Framework backend (chat, auth, attorney directory). Deployed to **Railway**.
- `frontend/` — Vue 3 + Vite SPA (chat UI). Deployed to **Cloudflare** (static `dist/` via Wrangler).
- `scrapers/uscis_scraper/` — Scrapy spider that crawls USCIS → **Cloudflare R2**. Runs weekly via GitHub Actions.
- `data/` — community-curated, per-country immigration knowledge/resources (Markdown + YAML) plus the scripts that validate and ingest them into the vector store.
- `config/.env` — the single env file read by **all** services (gitignored; see `config/.env.example`).

## Common commands

### Local development (Docker Compose — the primary workflow)
```bash
docker compose up                 # frontend :3000, api :8000 (uvicorn --reload), db :5432
docker compose up uscis_scraper   # run the scraper (also: --profile scraper)
docker compose down
```
Both the `api` and `frontend` images build with the **repo root as the build context** (so
`config/` is reachable); the dev API runs under **uvicorn/ASGI, not `runserver`**, because SSE
streaming requires an unbuffered ASGI server.

### API (`api/`, Poetry + a 3.10+ venv)
```bash
poetry install --with dev            # main deps + dev tools (pytest-django, ruff)
python manage.py migrate
python manage.py makemigrations
poetry run pytest                     # run all API tests (see below)
poetry run pytest -k semantic_search  # a single test by name
poetry run ruff check .               # lint (config in pyproject.toml)
```
Tests run under **pytest + pytest-django** (config in `[tool.pytest.ini_options]`): the settings
module is `api_project.dev` and `--no-migrations` builds the schema straight from the models —
so tests get isolated, empty tables and skip the reference-data migrations (which pre-populate
all countries via `pycountry` and load org fixtures). The unittest-style `SimpleTestCase` in
`conversation/tests.py` runs under pytest too. `.github/workflows/api-ci.yml` runs `ruff check`
+ `pytest` (against a Postgres service) on every PR touching `api/`.

### Frontend (`frontend/`)
```bash
npm install
npm run dev          # Vite dev server, :3000
npm run build        # vue-tsc typecheck + vite build → dist/
npm run lint         # ESLint (also lint:fix)
```
ESLint runs automatically **only** during `npm run dev` (via a Vite plugin); production builds
deliberately skip it, so run `npm run lint` yourself before shipping.

### Scraper (`scrapers/uscis_scraper/`)
```bash
pip install -r requirements.txt
scrapy crawl uscis   # LOCAL_TEST=true → writes ./output/ ; LOCAL_TEST=false → uploads to R2
pytest               # scraper unit tests
```

### Data corpus (from repo root)
```bash
pip install -r data/scripts/requirements.txt
python data/scripts/validate.py [cc]     # format gate (CI runs this on data/ PRs)
python data/scripts/ingest.py us         # DRY RUN: preview the chunks that would be upserted
python data/scripts/ingest.py us --upsert  # actually write to Pinecone (needs PINECONE_* env)
```

### Deploy
- **API → Railway**: `railway up --service visanav-api` builds the `production` stage of
  `api/Dockerfile` from the repo root. `api/entrypoint.sh` runs `migrate` + `collectstatic`
  (and optionally creates a superuser) on every container start. See README for the required
  env vars — `prod.py` refuses to boot without them.
- **Frontend → Cloudflare**: `npm run build` then `wrangler deploy` uploads `dist/` as a
  static-assets Worker (`frontend/wrangler.jsonc`, SPA fallback for Vue Router history mode).
- **Scraper → GitHub Actions**: `.github/workflows/scrape.yml` crawls weekly to R2.

## Architecture

### Configuration: one env file, loaded by relative path
There is a single `config/.env` at the repo root. Each service reaches it by walking up from
its own file location: `api/api_project/base.py`, the scraper's `settings.py`, and
`data/scripts/ingest.py` all `load_dotenv(<relative path to>/config/.env)`. **Moving those
files changes the relative depth and silently breaks env loading.** `config/.env.example`
documents every variable and is the source of truth for what each service reads.

### Django settings are split by environment
`api_project/base.py` holds shared settings; `dev.py` and `prod.py` import from it and override.
`DJANGO_SETTINGS_MODULE` selects which (`manage.py` defaults to `api_project.dev`; production
sets `api_project.prod`). `prod.py` hard-fails at startup if `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`,
or the `POSTGRES_*` vars are missing, and **reuses `CSRF_TRUSTED_ORIGINS` as `CORS_ALLOWED_ORIGINS`**
— that variable must include the frontend origin or the cross-origin chat calls are blocked.

### The RAG chat pipeline (the core feature)
1. The Vue chat UI POSTs to `/api/chat/` (`conversation/streaming.py`). This view is **`csrf_exempt`,
   async, and does its own JWT auth** (allowing anonymous users) and its own soft rate-limiting
   (LocMemCache, per-process — a cost cap, not a hard quota).
2. It drives the **pydantic-ai agent** built in `core/llm.py` (`get_agent()`, persona "Javi"),
   whose one tool, `semantic_search`, queries **Pinecone**. The namespace comes from `Deps`
   (`settings.PINECONE_NAMESPACE`, default `us`) — it **must** match a namespace that `ingest.py`
   populated, or retrieval silently returns nothing. The index *host* is `PINECONE_INDEX_HOST`.
3. Tokens stream back to the browser as **Server-Sent Events** (`status` / `delta` / `done` / `error`
   frames). This replaced an earlier Celery + Redis "enqueue and poll" design — **there is no Celery,
   no Redis, no Channels**; the cache is Django's in-process `LocMemCache`.
4. Conversation history is stored in Postgres as raw pydantic-ai message dicts in `Message.parts`
   (a `JSONField`) and rehydrated with `ModelMessagesTypeAdapter` on the next turn.

`core/llm.py` builds the model client and the Pinecone client **lazily** (`get_model()` /
`get_pinecone()`, both `@lru_cache`d, plus `get_agent()`), so importing `core.llm` needs no API
keys — management commands, migrations and tests import it fine, and a bad key surfaces on the
first chat request rather than crashing boot. `LLM_PROVIDER` (`anthropic` | `openai`) selects which
model is built; only the chosen provider's client is constructed.

### The data → vector store pipeline (two independent producers)
The Pinecone corpus is fed by two separate paths that do **not** currently connect to each other:
- **Curated knowledge** (`data/`): human-written Markdown+YAML under `data/countries/<cc>/`.
  `ingest.py` splits frontmatter, chunks the body (~200 words), and upserts into a **per-country
  namespace** with the frontmatter as metadata. `validate.py` gates format in CI (e.g. anything
  `source_type: official` must cite a domain declared in that country's `meta.yaml`).
- **Raw scrape** (`scrapers/`): the `uscis` spider crawls USCIS forms, the INA, and the Policy
  Manual, writing raw HTML/PDF/JSONL to R2 under `raw/`. It is **incremental** via a content-hash
  manifest (`raw/manifest.json`): `ContentHashPipeline` drops unchanged pages before they hit the
  storage sinks. This is raw archival — it is not yet wired into Pinecone.

### Django apps
- `accounts` — custom `User` (AbstractUser, `AUTH_USER_MODEL = accounts.User`) + `Profile`; JWT auth (SimpleJWT: 10-min access, 7-day refresh), registration, email verification.
- `conversation` — `Conversation` / `Message` / `Feedback` models, the `ConversationViewSet`, and the SSE `chat_stream`. Conversations are keyed publicly by **UUID, not integer id**, so anonymous chats can't be enumerated.
- `locations` — `Country` / `Subdivision` / `Address` / `Language` reference data.
- `network` — the attorney/organization directory (`Attorney`, `Organization` and its related contact/address/language models).
- `core` — shared infra: `llm.py` (the agent), `pagination.py`, `utils.py`, `mail.py`.

URL roots (`api_project/urls.py`): `api/` (conversation), `api/auth/`, `api/locations/`,
`api/network/`, and the Django admin at **`/nimda/`** (not `/admin/`).

### Frontend
Vue 3 `<script setup>` + Pinia + Vue Router + Tailwind v4, with shadcn-style UI primitives under
`src/components/ui/`. All API access goes through `API_BASE_URL` (`src/plugins/axios.ts`), sourced
from `VITE_API_BASE_URL` **baked in at build time**: unset in dev (Vite proxies `/api` →
`http://api:8000`), set to the absolute Railway/`api.visanav.org` URL in production. The axios client
auto-refreshes JWTs on 401 with a queued-request retry; the SSE chat stream uses native `fetch`
(not axios) but the same `API_BASE_URL`.

## Gotchas
- **Scraper + R2**: `AWS_USE_SSL = True` is set deliberately — with the default, botocore's
  S3 region-redirector infinitely recurses against R2. Don't remove it.
- **`pydantic-ai-slim`, not `pydantic-ai`**: only the `anthropic` + `openai` extras are installed
  to avoid pulling Bedrock → boto3 into the API image. `opentelemetry-api` is pinned `<1.37`
  because 1.37 removed a module pydantic-ai 0.7.x imports.
- **Default chat models** (`core/llm.py`): `claude-haiku-4-5` (anthropic) / `gpt-5-nano` (openai),
  overridable with `CHAT_MODEL`.
