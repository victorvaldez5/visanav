# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

VisaNav (a.k.a. "Project Raul" / immigration-ai) is a free immigration RAG chatbot that helps
immigrants find status/services and connect with free/low-cost public resources. It is a **monorepo of four
independently-deployed services** plus a shared config file:

- `api/` — Django REST Framework backend (chat, auth, public-resources directory). Deployed to **Railway**.
- `frontend/` — Vue 3 + Vite SPA (chat UI). Deployed to **Cloudflare** (static `dist/` via Wrangler).
- `scrapers/uscis_scraper/` — Scrapy spider that crawls USCIS → **Cloudflare R2**. Runs weekly via GitHub Actions.
- `data/` — community-curated, per-country immigration knowledge/resources (Markdown + YAML) plus the scripts that validate and ingest them into the vector store.
- `i18n/`: shared internationalization assets: the canonical locale allowlist (`supported-locales.json`) and the translation glossary. See "Internationalization" below.
- `config/.env` — the single env file read by **all** services (gitignored; see `config/.env.example`).

## Common commands

A root **`justfile`** wraps the everyday tasks (`just` lists them all): `just setup`,
`just test`, `just lint`, `just migrate`, `just manage <cmd>`, `just db-status`,
`just ingest us`, `just corpus-pull`, `just corpus-ingest`. Recipes run on the host
against the compose Postgres (`just db` starts only that). Prefer them over ad-hoc
commands; they never load `config/.env` into the shell.

### Python: one uv workspace
The Python services are members of a single **uv workspace** (root `pyproject.toml` +
one `uv.lock`): `api`, `scrapers/uscis_scraper` (`uscis-scraper`), and `data/scripts`
(`visanav-data`). There is **no Poetry and no requirements.txt**.
```bash
uv sync --all-packages      # dev: one repo-root .venv with every member + dev tools
uv run ruff check .         # lint (config lives in the ROOT pyproject.toml)
uv lock                     # after editing any member's dependencies
```
Each member declares only its own deps; images and CI install one member
(`uv sync --locked --package api --no-dev`), so the API image never ships Scrapy/boto3.
Python is pinned to 3.13 by `.python-version` (voyageai has no 3.14 wheel yet).

### Local development (Docker Compose — the primary workflow)
```bash
docker compose up                 # frontend :3000, api :8000 (uvicorn --reload), db :5432
docker compose up uscis_scraper   # run the scraper (also: --profile scraper)
docker compose down
```
Both the `api` and `frontend` images build with the **repo root as the build context** (so
`config/` is reachable); the dev API runs under **uvicorn/ASGI, not `runserver`**, because SSE
streaming requires an unbuffered ASGI server.

### API (`api/`)
```bash
just migrate                          # = cd api && uv run python manage.py migrate
just makemigrations
just test-api                         # all API tests (see below)
just test-api -k semantic_search      # a single test by name
```
Tests run under **pytest + pytest-django** (config in `[tool.pytest.ini_options]`): the settings
module is `api_project.dev` and `--no-migrations` builds the schema straight from the models —
so tests get isolated, empty tables and skip the reference-data migrations (which pre-populate
all countries via `pycountry` and load org fixtures). The unittest-style `SimpleTestCase` in
`conversation/tests.py` runs under pytest too. the `api` job in `.github/workflows/ci.yml` runs `ruff check`
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
just crawl           # LOCAL_TEST=true crawl → scrapers/uscis_scraper/output/ (never R2)
just test-scraper    # scraper unit tests
```
(`LOCAL_TEST=false` uploads to R2; only the weekly `scrape.yml` job runs that way.)

### Data corpus
```bash
# Validation + chunk preview (dependency-light, no keys/DB — this is all CI needs):
just validate-data [cc]                  # format gate (CI runs this on data/ PRs)
uv run python data/scripts/ingest.py us  # preview the chunks (dry run only)

# Authoritative ingestion (embed via Voyage + write to pgvector) lives in the API:
just ingest us --dry     # DRY RUN: chunk + preview, no keys/DB
just ingest us           # embed + upsert curated data/ (needs VOYAGE_API_KEY + DB)
just corpus-pull         # fetch the crawl's JSONL feeds from R2 (needs R2 read creds)
just corpus-ingest       # embed + upsert the scraped USCIS corpus from those feeds
just db-status           # chunk counts per country / corpus / topic
```
Both ingest commands transactionally replace **only their own corpus** (the
`KnowledgeChunk.corpus` column: `curated` vs `uscis`), so re-running one never wipes the
other. Run them from a full checkout (local/CI), not the prod web image.

### Translations (i18n)
```bash
just check-i18n     # = node scripts/check_i18n_parity.mjs: locale lists + defaults + catalog parity (CI: the `i18n` job in `ci.yml`)
```

### Deploy
- **API → Railway**: `railway up --service visanav-api` builds the `production` stage of
  `api/Dockerfile` from the repo root. Railway runs `migrate` as a pre-deploy command
  (`railway.json`; the service sets `SKIP_MIGRATE_ON_START=1`), and `api/entrypoint.sh` runs `collectstatic`
  (and optionally creates a superuser) on every container start. Release steps: `docs/RELEASING.md`. See README for the required
  env vars — `prod.py` refuses to boot without them.
- **Frontend → Cloudflare**: `npm run build` then `wrangler deploy` uploads `dist/` as a
  static-assets Worker (`frontend/wrangler.jsonc`, SPA fallback for Vue Router history mode).
- **Scraper → GitHub Actions**: `.github/workflows/scrape.yml` crawls weekly to R2.

## Architecture

### Configuration: one env file, loaded by relative path
`config/.env` works both on the host and in containers: it does **not** set `POSTGRES_HOST`
(Django defaults to `localhost`, the compose db's published port), and `docker-compose.yml`
sets `POSTGRES_HOST=db` for the `api` container only. Don't put `POSTGRES_HOST=db` back in
the env file, or every host-side command loses the database.

There is a single `config/.env` at the repo root. Each service reaches it by walking up from
its own file location: `api/api_project/base.py` and the scraper's `settings.py` both
`load_dotenv(<relative path to>/config/.env)`. **Moving those files changes the relative depth
and silently breaks env loading.** `config/.env.example` documents every variable and is the
source of truth for what each service reads. (The `manage.py ingest` command reads env via
Django settings; the standalone `data/scripts/ingest.py` is now dry-run-only and needs no env.)

**Git-worktree footgun:** `config/.env` is gitignored, so it exists only in the checkout it was
created in — a fresh `git worktree` starts with **no** env file, and every service then silently
loads nothing (no error, just missing settings: a blank `DJANGO_SECRET_KEY`, absent API keys,
etc.). Symlink it from the primary checkout before running anything in a worktree, from the
worktree root:
```bash
ln -s "$(git worktree list --porcelain | sed -n 's/^worktree //p' | head -1)/config/.env" config/.env
```
(the primary checkout is the first `git worktree list` entry.) The symlink is itself gitignored,
so it never shows in `git status` and must be recreated for each new worktree.

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
   which has two tools: `semantic_search` embeds the query via **Voyage** (`core/embeddings.py`)
   and ranks the **pgvector** `KnowledgeChunk` table by cosine distance, scoped to a country from
   `Deps` (`settings.KNOWLEDGE_COUNTRY`, default `us` — it **must** match a country `ingest`
   populated, or retrieval returns nothing); and `resource_lookup` queries the `network.Organization`
   directory directly over the ORM (US-only for now) to surface free/low-cost nonprofit and pro-bono help.
   `Deps` also carries the reply `locale` (`request.LANGUAGE_CODE`, see "Internationalization"), which
   a dynamic instruction (`language_instructions`) gives to Javi each turn as the default reply language.
3. Tokens stream back to the browser as **Server-Sent Events** (`status` / `delta` / `done` / `error`
   frames). This replaced an earlier Celery + Redis "enqueue and poll" design — **there is no Celery,
   no Redis, no Channels**; the cache is Django's in-process `LocMemCache`.
4. Conversation history is stored in Postgres as raw pydantic-ai message dicts in `Message.parts`
   (a `JSONField`) and rehydrated with `ModelMessagesTypeAdapter` on the next turn.

`core/llm.py` builds the model client **lazily** (`get_model()` + `get_agent()`, `@lru_cache`d),
and `core/embeddings.py` builds the Voyage client the same way (`get_voyage_client()`), so
importing them needs no API keys — management commands, migrations and tests import them fine, and
a bad key surfaces on the first embed/chat request rather than crashing boot. `LLM_PROVIDER`
(`anthropic` | `openai`) selects which chat model is built; only the chosen provider's client is
constructed. Embeddings are a **separate** concern from the chat provider (Anthropic has no
embeddings API): `EMBEDDING_MODEL` (default `voyage-3`, 1024-dim) is always Voyage.

### The data → vector store pipeline (two producers)
The pgvector corpus (`knowledge.KnowledgeChunk`) is fed by two separate paths, each owning
its rows via the `corpus` column:
- **Curated knowledge** (`data/`): human-written Markdown+YAML under `data/countries/<cc>/`.
  The `manage.py ingest` command (chunking in `knowledge/ingest_utils.py`) splits frontmatter,
  chunks the body (~200 words), embeds via Voyage, and upserts rows scoped by **country** with the
  frontmatter as columns. `validate.py` gates format in CI (e.g. anything `source_type: official`
  must cite a domain declared in that country's `meta.yaml`).
- **Raw scrape** (`scrapers/`): the `uscis` spider crawls USCIS forms, the INA, and the Policy
  Manual, writing raw HTML/PDF/JSONL to R2 under `raw/`. It is **incremental** via a content-hash
  manifest (`raw/manifest.json`): `ContentHashPipeline` drops unchanged pages before they hit the
  storage sinks, and every crawl also writes a JSONL feed (`raw/items/uscis/<time>.jsonl`, url +
  main-content HTML). Because feeds are deltas, `manage.py ingest_scrape` (`knowledge/scrape_utils.py`)
  merges **all** of them oldest→newest, extracts the Policy Manual guidance, INA statute text and
  form pages, and writes `corpus="uscis"` chunks. PDFs aren't ingested yet.

### Django apps
- `accounts` — custom `User` (AbstractUser, `AUTH_USER_MODEL = accounts.User`) + `Profile`; JWT auth (SimpleJWT: 10-min access, 7-day refresh), registration, email verification.
- `conversation` — `Conversation` / `Message` / `Feedback` models, the `ConversationViewSet`, and the SSE `chat_stream`. Conversations are keyed publicly by **UUID, not integer id**, so anonymous chats can't be enumerated.
- `locations` — `Country` / `Subdivision` / `Address` / `Language` reference data.
- `network` — the public-resources directory: a flat `Organization` (contact details are inline Postgres `ArrayField`s — no contact/address/language side-tables — matching `data/schema/resource.schema.json`) plus a read-only `Representative` (individual attorneys / DOJ-accredited reps). Seeded via management commands (`load_resources <cc>`, `extract_ra_orgs`, `extract_probono`, `extract_ra_reps`), not migrations; the DOJ roster fixtures are (re)parsed from the source EOIR PDFs in `data/raw/` by `build_ra_fixtures` (`download_ra_rosters`, or `build_ra_fixtures --download`, refreshes those PDFs from justice.gov first).
- `knowledge` — the pgvector RAG corpus: `KnowledgeChunk` (embedded chunks, per-country), `ingest_utils.py` (chunking), and the `ingest` management command.
- `core` — shared infra: `llm.py` (the agent), `embeddings.py` (Voyage), `pagination.py`, `utils.py`, `mail.py`.

URL roots (`api_project/urls.py`): `api/` (conversation), `api/auth/`, `api/locations/`,
`api/network/`, and the Django admin at **`/nimda/`** (not `/admin/`).

### Frontend
Vue 3 `<script setup>` + Pinia + Vue Router + Tailwind v4, with shadcn-style UI primitives under
`src/components/ui/`. All API access goes through `API_BASE_URL` (`src/plugins/axios.ts`), sourced
from `VITE_API_BASE_URL` **baked in at build time**: unset in dev (Vite proxies `/api` →
`http://api:8000`), set to the absolute Railway/`api.visanav.org` URL in production. The axios client
auto-refreshes JWTs on 401 with a queued-request retry; the SSE chat stream uses native `fetch`
(not axios) but the same `API_BASE_URL`. Both send `Accept-Language` from the active UI locale
(`currentLocale()` in `src/i18n/index.ts`).

### Internationalization
Language localization of the US product: English + Spanish now, `zh-Hans` next. The design,
phases, and the "Adding a locale" checklist are in `docs/i18n-architecture.md`.
- **One allowlist:** `i18n/supported-locales.json` is the source of truth. Django `LANGUAGES` +
  `LANGUAGE_CODE` and the frontend's `SUPPORTED_LOCALES` + `DEFAULT_LOCALE` mirror it, and
  `scripts/check_i18n_parity.mjs` (CI: the `i18n` job in `ci.yml`) fails when they drift or a catalog has gaps.
- **Transport:** `LocaleMiddleware` maps the `Accept-Language` header onto `LANGUAGES`, so
  `request.LANGUAGE_CODE` is always an allowlisted code (falling back to `en`). There are no
  `i18n_patterns`, so no URL-prefix redirects.
- **Catalogs:** the frontend's vue-i18n messages are `src/locales/<code>.json`; Django gettext
  catalogs go under `api/locale/` (empty until API strings are wrapped in `_()`); shared domain
  terms are in `i18n/GLOSSARY.md`.

## Gotchas
- **Docker images install into `/opt/venv`** (on `PATH`), outside `/app`, so the dev bind mount
  can't shadow it. Never start container commands via `bash -lc`: a login shell resets `PATH`
  and `python` silently loses every package. Build context is the repo root, so the root
  `.dockerignore` is the only one Docker reads (it keeps `.venv`, `node_modules`, `.claude/`
  and `config/.env` out of the context).
- **Scraper + R2**: `AWS_USE_SSL = True` is set deliberately — with the default, botocore's
  S3 region-redirector infinitely recurses against R2. Don't remove it.
- **`pydantic-ai-slim`, not `pydantic-ai`**: only the `anthropic` + `openai` extras are installed
  to avoid pulling Bedrock → boto3 into the API image. `opentelemetry-api` is pinned `<1.37`
  because 1.37 removed a module pydantic-ai 0.7.x imports.
- **Default chat models** (`core/llm.py`): `claude-haiku-4-5` (anthropic) / `gpt-5-nano` (openai),
  overridable with `CHAT_MODEL`.
- **pgvector needs a pgvector-capable Postgres**: `docker-compose` and CI use `pgvector/pgvector:pg15`
  (not `postgres:*-alpine`). The `knowledge` initial migration runs `CREATE EXTENSION vector` (so
  Railway's pre-deploy `migrate` sets it up), but tests run `--no-migrations` (schema from models),
  so `api/conftest.py` seeds the `vector` extension into `template1` before the test DB is created.
- **Embeddings ≠ chat provider**: retrieval always embeds with **Voyage** (`EMBEDDING_MODEL`,
  1024-dim) regardless of `LLM_PROVIDER` (Anthropic has no embeddings API). `voyage-3` ↔ `voyage-law-2`
  are both 1024-dim, so swapping them is env + re-ingest, no migration; other dims need a migration.
- **voyageai has no Python 3.14 wheel** yet — pinned with a `python = "<3.14"` marker in
  `pyproject.toml`; the deploy/CI runtime is 3.13, so this is a non-issue there.
