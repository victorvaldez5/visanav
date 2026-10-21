# VisaNav task runner. `just` lists every recipe along with its comment below.
#
# Recipes run on the host against the docker-compose Postgres (localhost:5432).
# Nothing here loads config/.env into the shell: each service reads it itself,
# so secrets never land in recipe environments or command echoes.

set shell := ["bash", "-euo", "pipefail", "-c"]

# The feeds root: one directory of JSONL feeds per scrape source.
feeds := "scrapers/uscis_scraper/output/items"

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

# What's in the vector store, how fresh each corpus is, and the resource directory size
db-status: db
    @cd api && uv run python manage.py corpus_status
    @cd api && uv run python manage.py shell -v 0 -c "from network.models import Organization as O; print(f'organizations: {O.objects.count()}')"

# Ingest everything that is due, as the scheduler does: curated data/ if it changed, and each scrape source's new feeds straight from R2
corpus-refresh *args: db
    cd api && uv run python manage.py refresh_corpus {{args}}

# Embed + upsert the curated data/ corpus for a country (dry run: add --dry; other flags, such as --force, pass through)
ingest cc="us" *flags: db
    #!/usr/bin/env bash
    set -euo pipefail
    mode="--upsert"; flags=()
    for arg in {{flags}}; do
        if [ "$arg" = "--dry" ]; then mode=""; else flags+=("$arg"); fi
    done
    # (macOS bash 3.2 rejects an empty array under `set -u`, hence the guard.)
    cd api && uv run python manage.py ingest {{cc}} $mode ${flags[@]+"${flags[@]}"}

# Download the crawls' JSONL feeds from R2, every source or just those named (needs R2 read credentials in config/.env)
corpus-pull *sources:
    cd scrapers/uscis_scraper && uv run python pull_feeds.py {{sources}}

# Embed + upsert the scraped corpus from the pulled feeds: every source, or just those named (dry run: add --dry; other flags, such as --force, pass through)
corpus-ingest *args: db
    #!/usr/bin/env bash
    set -euo pipefail
    mode="--upsert"; sources=()
    for arg in {{args}}; do
        case "$arg" in
            --dry) mode="" ;;
            --*) sources+=("$arg") ;;
            *) sources+=(--source "$arg") ;;
        esac
    done
    # (macOS bash 3.2 rejects an empty array under `set -u`, hence the guard.)
    cd api && uv run python manage.py ingest_scrape ../{{feeds}} $mode ${sources[@]+"${sources[@]}"}

# Run one source's crawl locally into scrapers/uscis_scraper/output/ (never touches R2): uscis, ecfr or federal-register
crawl source="uscis":
    cd scrapers/uscis_scraper && LOCAL_TEST=true uv run scrapy crawl {{source}}

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
