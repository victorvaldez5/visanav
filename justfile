# VisaNav task runner. `just` lists every recipe along with its comment below.
#
# Recipes run on the host against the docker-compose Postgres (localhost:5432).
# Nothing here loads config/.env into the shell: each service reads it itself,
# so secrets never land in recipe environments or command echoes.

set shell := ["bash", "-euo", "pipefail", "-c"]

feeds := "scrapers/uscis_scraper/output/items/uscis"

# List recipes
default:
    @just --list --unsorted

# ── setup ────────────────────────────────────────────────────────────────────

# Install every Python service + dev tools into one .venv, and the frontend deps
setup: env-check
    uv sync --all-packages
    cd frontend && npm install

# Fail fast if config/.env is missing (e.g. in a fresh git worktree)
env-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -e config/.env ]; then
        echo "config/.env is missing. Copy config/.env.example, or in a git worktree run: just env-link" >&2
        exit 1
    fi

# In a git worktree, symlink config/.env from the primary checkout
env-link:
    #!/usr/bin/env bash
    set -euo pipefail
    primary="$(git worktree list --porcelain | sed -n 's/^worktree //p' | head -1)"
    if [ "$primary" = "$PWD" ]; then echo "already the primary checkout"; exit 0; fi
    ln -sfn "$primary/config/.env" config/.env
    echo "linked config/.env -> $primary/config/.env"

# ── run ──────────────────────────────────────────────────────────────────────

# Start the full stack: frontend :3000, api :8000, db :5432
up *args:
    docker compose up {{args}}

# Stop the stack
down:
    docker compose down

# Start just Postgres (enough for host-side manage.py, tests and ingest)
db:
    docker compose up -d db

# Run any manage.py command on the host, e.g. `just manage createsuperuser`
manage *args: db
    cd api && uv run python manage.py {{args}}

# Refresh the API's gettext catalogs: extract new `_()` strings into the .po files,
# then (after translating them) compile the .mo files that Django actually loads.
# Both are committed; a test fails if a .mo is missing or stale.
messages: (manage "makemessages" "-a" "--no-location" "--no-wrap" "--ignore" ".venv/*")
compile-messages: (manage "compilemessages")

migrate: (manage "migrate")

makemigrations *args: (manage "makemigrations" args)

# ── quality ──────────────────────────────────────────────────────────────────

# Lint all Python (ruff, repo-wide config) and the frontend (eslint)
lint:
    uv run ruff check .
    cd frontend && npm run lint

# Run every test suite (pass pytest args to a single suite via test-api etc.)
test: test-api test-scraper validate-data check-i18n test-frontend

# API tests (needs the db), e.g. `just test-api -k semantic_search`
test-api *args: db
    cd api && uv run pytest {{args}}

# Scraper unit tests, e.g. `just test-scraper -k manifest`
test-scraper *args:
    cd scrapers/uscis_scraper && uv run pytest {{args}}

test-frontend:
    cd frontend && npm test

# i18n consistency: locale allowlist, catalog key parity, complete .po files
check-i18n:
    node scripts/check_i18n_parity.mjs

# Validate the curated data/ corpus format (optionally one country: `just validate-data us`)
validate-data *cc:
    uv run python data/scripts/validate.py {{cc}}

# ── knowledge corpus ─────────────────────────────────────────────────────────

# What's in the vector store and resource directory right now
db-status: db
    @cd api && uv run python manage.py shell -v 0 -c "from django.db.models import Count; from knowledge.models import KnowledgeChunk as K; from network.models import Organization as O; rows = K.objects.values('country', 'corpus', 'topic').annotate(n=Count('id')).order_by('country', 'corpus', 'topic'); [print(f\"{r['country']:3} {r['corpus']:8} {r['topic'] or '-':16} {r['n']:6}\") for r in rows]; print(f\"total chunks: {K.objects.count()}   organizations: {O.objects.count()}\")"

# Embed + upsert the curated data/ corpus for a country (dry run: add --dry)
ingest cc="us" *flags: db
    cd api && uv run python manage.py ingest {{cc}} {{ if flags == "--dry" { "" } else { "--upsert" } }}

# Download the crawl's JSONL feeds from R2 (needs R2 read credentials in config/.env)
corpus-pull:
    cd scrapers/uscis_scraper && uv run python pull_feeds.py

# Embed + upsert the scraped USCIS corpus from the pulled feeds (dry run: add --dry)
corpus-ingest *flags: db
    cd api && uv run python manage.py ingest_scrape ../{{feeds}} {{ if flags == "--dry" { "" } else { "--upsert" } }}

# Run the USCIS crawl locally into scrapers/uscis_scraper/output/ (never touches R2)
crawl:
    cd scrapers/uscis_scraper && LOCAL_TEST=true uv run scrapy crawl uscis

# ── frontend ─────────────────────────────────────────────────────────────────

# Vite dev server on :3000 (outside docker)
fe-dev:
    cd frontend && npm run dev

# Typecheck + production build to frontend/dist
fe-build:
    cd frontend && npm run build

# ── release ──────────────────────────────────────────────────────────────────

# What would ship (commits, migrations, new env vars, CI status); add --local to run checks here
release-check *args:
    scripts/release.sh check {{args}}

# Merge develop into main and tag vYYYY.MM.DD (checks CI, confirms first); -y skips the prompt, --local runs checks here
release *args:
    scripts/release.sh {{args}}
