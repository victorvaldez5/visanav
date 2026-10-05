# Plan: move the USCIS scraper from GitHub Actions to a Railway cron service

Status: proposed. Branch `feat/scraper-railway-migration`, based on `develop`.

## Why

The weekly crawl (`.github/workflows/scrape.yml`) takes about 114 minutes on a
GitHub-hosted runner, which is metered because the repo is private. That is roughly
460 to 570 minutes a month for one source, against a 2,000 minute budget that PR CI
also draws on. By late September the budget ran out and every workflow, including the
Sep 28 scrape, failed with "recent account payments have failed or your spending limit
needs to be increased".

The runtime is mostly deliberate sleeping: `DOWNLOAD_DELAY = 5` with AutoThrottle
targeting one concurrent request per host (`scrapers/uscis_scraper/uscis_scraper/settings.py`).
That politeness toward USCIS is correct and should not change. What should change is
where the waiting happens. Railway bills for resources used, and an idle crawler
uses almost none. More sources are planned, so the metered runner scales badly.

## What already exists (and is reused)

| Piece | Where | Note |
|---|---|---|
| Production image stage | `scrapers/uscis_scraper/Dockerfile` (`production`) | Installs only `uscis-scraper` deps, bakes in code, `CMD scrapy crawl uscis`. Built with repo root as context. |
| Shallow-path env handling | `settings.py` (`len(_parents) > 3`) | In the image the code is at `/app/uscis_scraper/`, so `config/.env` is skipped and real env vars are used. This is what Railway variables will feed. |
| Railway cron pattern | `railway.cron.json` | Today it runs `purge_expired_conversations` daily on the API image. Same mechanism, different image and command. |
| Incremental crawl | `ContentHashPipeline`, `raw/manifest.json` in R2 | State lives in R2, not on the box, so a Railway container with no volume is fine and a killed run just resumes next week. |

## Target shape

```
Railway project "visanav"
  visanav-api            (existing, web, api/Dockerfile production stage)
  Postgres               (existing)
  purge cron             (existing, railway.cron.json, daily 07:00 UTC)
  visanav-scraper-uscis  (NEW, cron, scrapers/uscis_scraper/Dockerfile production stage)
```

The scraper service is its own Railway service, built from the repo root, running
`scrapy crawl uscis` on a weekly cron and exiting when done.

## Changes

### 1. Railway config for the scraper (new file)

Add `scrapers/uscis_scraper/railway.json`:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "scrapers/uscis_scraper/Dockerfile"
  },
  "deploy": {
    "cronSchedule": "0 6 * * 1",
    "numReplicas": 1,
    "restartPolicyType": "NEVER"
  }
}
```

Notes:

- Keep the existing Monday 06:00 UTC schedule so behavior is unchanged.
- `restartPolicyType: NEVER`, matching the purge cron. A crawl that fails should wait
  for the next scheduled run, not hammer USCIS in a retry loop.
- The build target must be `production`. The Dockerfile's last stage is `production`,
  so the default target is right, but pass nothing that selects `development`.
- Each service points at its own config file via the service's "Config as code" path
  setting in the dashboard (root `railway.json` and `railway.cron.json` are already
  claimed by other services). Verify the path is resolved from the repo root and that
  the Docker build context stays at the root, since the Dockerfile `COPY`s
  `./pyproject.toml`, `./uv.lock` and the other workspace manifests.

### 2. Service variables (no secrets in the repo)

Set on the new service, same names `settings.py` already reads:

| Variable | Value |
|---|---|
| `LOCAL_TEST` | `false` (default is `True`, which would write into the container and discard it) |
| `R2_BUCKET` | existing bucket |
| `AWS_ENDPOINT_URL` | existing R2 endpoint |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | an R2 token scoped to object read and write on this bucket only |
| `AWS_REGION_NAME` | `auto` |

Create a dedicated R2 API token for the scraper rather than copying the one in
GitHub secrets, so the GitHub copy can be revoked at cutover. Do not paste any of
these values into chat, commits or logs.

### 3. Fix the `LOCAL_TEST` default for production images

`LOCAL_TEST` defaults to true, so a Railway service missing that one variable
silently crawls into an ephemeral directory and reports success. Options, in order
of preference:

1. Set `ENV LOCAL_TEST=false` in the `production` Docker stage only. The development
   stage and compose keep the safe local default.
2. Or make the spider fail fast when running a production image without R2 settings.

Option 1 is a one-line change and removes the failure mode.

### 4. Cut over `scrape.yml`

Do this only after one successful Railway run:

1. Remove the `schedule:` trigger from `.github/workflows/scrape.yml`. Keep
   `workflow_dispatch` as a manual fallback for a few weeks, then decide whether to
   delete the file.
2. Revoke or remove the R2 secrets from GitHub once the fallback is retired.

Do not do both at once. Two scheduled crawlers against the same manifest would race
on `raw/manifest.json`.

### 5. Pin the runner image

PR CI also drew on the minute budget, but that is already handled: PR #35
consolidated the five CI workflows into `.github/workflows/ci.yml`, which has a
`concurrency` group that cancels superseded PR runs and a `dorny/paths-filter`
step so each area job runs only when its paths changed. Nothing more to do there.

What remains is one small change: pin `runs-on: ubuntu-24.04` instead of
`ubuntu-latest` in `ci.yml` (every job) and `scrape.yml`. GitHub is moving the
`ubuntu-latest` label to Ubuntu 26 on Oct 19, 2026. Since `scrape.yml` becomes a
manual fallback, pinning it keeps the fallback from breaking silently.

### 6. Docs

- `CLAUDE.md`: update the repo overview line ("Runs weekly via GitHub Actions"), the
  "Scraper" command note ("only the weekly `scrape.yml` job runs that way"), and the
  Deploy section ("Scraper -> GitHub Actions").
- `README.md` (line ~115 "Scheduling"): describe the Railway cron service, and add a
  short "Deploying the scraper (Railway)" section next to the API one.
- `config/.env.example` (line ~81): the comment already names Railway cron as an
  option, so point it at the new section.

## Out of scope here, worth deciding separately

### Chaining ingestion after the crawl

Today the crawl output reaches pgvector only by hand (`just corpus-pull` then
`just corpus-ingest`). `manage.py ingest_scrape` needs Django, Postgres and Voyage,
none of which are in the scraper image (by design: the API image never ships Scrapy,
and the scraper image never ships Django).

So automating it means a second cron service on the **API** image, scheduled some
hours after the crawl, running `ingest_scrape` against R2 feeds. Railway cron has no
job dependencies, so ordering is by schedule offset only (crawl is about 2 hours, so
start ingestion at least 3 hours later). That service needs read-only R2 credentials,
`VOYAGE_API_KEY` and the database. Note `CLAUDE.md` says the ingest commands should
run from a full checkout rather than the prod web image, so check whether
`pull_feeds.py` and `ingest_scrape` work in the API image before committing to this.

Recommendation: ship the scraper move first, run it a few weeks, then do this as its
own PR.

### Adding more scrape sources

The current layout is one Scrapy project per source (`scrapers/uscis_scraper/`).
Before adding a second source, decide between:

- a second spider in the same project (shared pipelines and manifest logic, one image,
  one Railway service per spider via a different `startCommand`), or
- a second project under `scrapers/` (isolated deps, isolated image).

A shared project with one cron service per spider is likely the cheaper option. The
manifest key would also need to be namespaced per source (it is a single
`raw/manifest.json` today).

## Risks and checks

| Risk | Mitigation |
|---|---|
| Missing `LOCAL_TEST=false` makes the crawl succeed while writing nothing to R2 | Change 3 above, plus verify objects and a new `raw/items/uscis/<time>.jsonl` after the first run. |
| Cron overlap: Railway skips a run if the previous one is still going | Crawl is about 2 hours on a weekly schedule, so low risk. Watch for it if sources are added. |
| Config-as-code path or build context wrong, so the image cannot find `uv.lock` | Do a manual deploy and read the build log before relying on the schedule. |
| Both schedulers active during cutover | Sequence in change 4: Railway succeeds first, then remove the GitHub schedule. |
| Crawl killed mid-run | Unverified. The manifest is saved in `ContentHashPipeline` (see `_save_manifest`); read when it is written (on close only, or periodically) to learn whether a killed run loses its progress or marks unwritten items as seen. |
| Cost surprises | Check Railway's usage page after the first run and set a usage limit on the project. |

## Verification checklist

1. `docker build -f scrapers/uscis_scraper/Dockerfile --target production .` from the
   repo root succeeds locally.
2. `just test-scraper` passes.
3. Create the Railway service, set variables, trigger one manual run, and confirm:
   exit code 0, R2 has a fresh `raw/items/uscis/*.jsonl`, `raw/manifest.json` updated.
4. Let one scheduled Monday run succeed, then apply change 4.
5. After a few weeks, retire the `workflow_dispatch` fallback and the GitHub R2 secrets.

## Order of work

1. Add `scrapers/uscis_scraper/railway.json` and the `ENV LOCAL_TEST=false` line in the
   `production` stage.
2. Local image build and `just test-scraper`.
3. Docs updates.
4. Pin `ubuntu-24.04` in `ci.yml` and `scrape.yml` (change 5).
5. Open PR into `develop`. Railway setup and the manual first run happen in the
   dashboard and CLI, not in the PR.
6. After a verified Railway run: remove the `schedule:` trigger (a small follow-up commit).
