# Plan: move the USCIS scraper from GitHub Actions to a Railway cron service

Status: in progress. Branch `feat/scraper-railway-migration`, based on `develop`.

> **Update (Railway deprecated Config as Code).** New services cannot use `railway.json`, and
> existing config files stop working on **2026-12-01**. The scraper therefore does not get a
> `railway.json`. Its service is defined in `.railway/railway.ts` (Infrastructure as Code) and
> configured in the dashboard. Section 1 below describes that, and the section 4 cutover is
> unchanged. The live service is named `visanav-scraper` and the API service is `visanav`.

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
| Cron services | Railway cron | `railway.cron.json` describes a daily `purge_expired_conversations` job on the API image, but no such service exists in the production environment today (see "Railway deprecation"). |
| Incremental crawl | `ContentHashPipeline`, `raw/manifest.json` in R2 | State lives in R2, not on the box, so a Railway container with no volume is fine and a killed run just resumes next week. |

## Target shape

```
Railway project "jubilant-success", environment "production"
  visanav          (existing, web, api/Dockerfile production stage, api.visanav.org)
  Postgres         (existing, managed; not declared in .railway/railway.ts)
  visanav-scraper  (NEW, cron, scrapers/uscis_scraper/Dockerfile production stage)
```

The scraper service is its own Railway service, built from the repo root, running
`scrapy crawl uscis` on a weekly cron and exiting when done.

## Changes

### 1. Railway service definition (IaC, not `railway.json`)

The service is declared in `.railway/railway.ts`:

```ts
const visanavScraper = service("visanav-scraper", {
  source: github("victorvaldez5/visanav", { branch: "feat/scraper-railway-migration", checkSuites: false }),
  build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/scrapers/uscis_scraper/Dockerfile" },
  deploy: { cronSchedule: "0 6 * * 1", restartPolicyType: "NEVER" },
  env: { R2_BUCKET: preserve(), /* ...credentials stay on Railway... */ },
});
```

Notes:

- The file was produced by `railway config pull` from the live project, then trimmed to
  the two services built from this repo (API and scraper). It sets `export const partial`,
  so a plan or apply never touches Postgres or its volume. `railway config plan` against
  production reports no changes, so the file matches what is deployed today.
- Keep the Monday 06:00 UTC schedule so behavior is unchanged. `NEVER` means a failed
  crawl waits for the next run instead of retrying against USCIS.
- Leave the service's Root Directory empty. The Dockerfile `COPY`s `./pyproject.toml`,
  `./uv.lock` and the other workspace manifests from the repo root.
- **Before merging to `main`**, the scraper's `source.branch` must stop pointing at
  `feat/scraper-railway-migration` (delete the `branch` option so it follows the default
  branch like the API service). Do that in the same change that merges the feature branch,
  and run `railway config plan` first.
- Nothing applies this file automatically. `railway config apply` is a manual, confirmed
  step. Railway does not allow a service to be managed by both Config as Code and IaC, so
  the API's move off the root `railway.json` is a deliberate cutover (see below).

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

## Railway deprecation: Config as Code ends 2026-12-01

Railway deprecated Config as Code (`railway.json` / `railway.toml`). New services cannot
opt in, and existing files stop working on 2026-12-01. What that means here:

- **Scraper:** no `railway.json`. It is defined in `.railway/railway.ts`, which `railway
  config pull` generated from the live service and `railway config plan` confirms is in sync.
- **API (`visanav`):** still driven by the root `railway.json` (Dockerfile path, pre-deploy
  `migrate`, restart policy). `.railway/railway.ts` already declares it with the same
  Dockerfile path and pre-deploy command, but it has **not been applied**, and the live
  service has no restart policy in the pulled state (the `railway.json` one is
  `ON_FAILURE`, 3 retries). Cutting over means `railway config apply` (and clearing the
  service's config-file setting), which is a production change to do deliberately, well
  before 2026-12-01, after reading `railway config plan`.
- **`railway.cron.json`:** it describes a daily `purge_expired_conversations` job, but the
  production environment has **no purge service** (only `visanav`, `visanav-scraper` and
  Postgres). Either the retention purge is not running in production or it runs somewhere
  not visible from this project. This needs a decision: add a purge cron service (declare
  it in `.railway/railway.ts` with `cronSchedule`), or delete the stale file.
- **Names:** the live services are `visanav` (API) and `visanav-scraper`. Some docs and
  `railway up --service visanav-api` examples use older names.

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

1. Define the service in `.railway/railway.ts` and add the `ENV LOCAL_TEST=false` line in
   the `production` stage.
2. Local image build and `just test-scraper`.
3. Docs updates.
4. Pin `ubuntu-24.04` in `ci.yml` and `scrape.yml` (change 5).
5. Open PR into `develop`. The manual first run and any `railway config apply` happen in
   the dashboard and CLI, not in the PR.
6. After a verified Railway run: remove the `schedule:` trigger (a small follow-up commit).
