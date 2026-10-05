# Releasing VisaNav

A release is a `develop` → `main` merge PR. Merging to `main` is what ships: the
frontend builds on Cloudflare, the API redeploys on Railway, and the weekly
scraper runs from `main`. Use the PR body of #30 as the template for the
description (one part per theme, a checklist, and how it was verified).

This is a checklist, not automation. Copy the sections you need into the release
PR description and tick them off.

## 1. Decide what ships

- [ ] `git log --oneline --no-merges origin/main..develop` reviewed. Every commit
      is something you want in production **now**.
- [ ] Nothing half-finished is user-visible. Staged work (for example the i18n
      phases) is either behind a flag or its launch gate has been met.
- [ ] `develop` is up to date and the working tree is clean.

## 2. CI and local checks

- [ ] CI is green on the latest `develop` commit (api-ci, frontend-ci, i18n-ci,
      scraper-ci, validate-data). If Actions minutes are exhausted, run the local
      equivalents below instead and say so in the PR.
- [ ] `just lint`
- [ ] `just test`
- [ ] `just check-i18n`
- [ ] `just validate-data`
- [ ] `cd frontend && npm run lint && npm run build` (production builds skip ESLint,
      so run it yourself).
- [ ] The production image builds from the repo root:
      `docker build -f api/Dockerfile --target production .`
      (catches a stale `uv.lock` or a broken Dockerfile before Railway does).

## 3. Migrations and data

List every migration in the release:

```bash
git diff --name-only origin/main...develop | grep migrations/
```

- [ ] `just manage makemigrations --check --dry-run` reports no missing migrations.
- [ ] Each migration is classified in the PR as **additive** (new nullable or
      defaulted column or table) or **destructive / irreversible** (drops rows,
      drops columns, reverse is a noop).
- [ ] Destructive migrations have a stated reason, and a database backup was taken
      first (Railway Postgres → Backups, or `pg_dump`).
- [ ] Migrations that touch large tables were considered for lock time.
- [ ] The migration is compatible with the **previous** code, so a rollback of the
      app (not the schema) still works. Prefer a two-step release for renames and
      drops.
- [ ] Any one-off data step is written down (for example `just corpus-pull` then
      `just corpus-ingest` after a `KnowledgeChunk` change, or `load_resources`).
      Say who runs it and when relative to the deploy.

## 4. Configuration

- [ ] `git diff origin/main...develop -- config/.env.example` reviewed. Every new
      variable is set on the right service before merging: Railway (API), Cloudflare
      (frontend build vars such as `VITE_API_BASE_URL`), GitHub Actions secrets
      (scraper).
- [ ] `CSRF_TRUSTED_ORIGINS` still includes the frontend origin (it doubles as
      `CORS_ALLOWED_ORIGINS`).
- [ ] The API service has `SKIP_MIGRATE_ON_START=1` set (migrations run in the
      pre-deploy command, see below).
- [ ] No secret values in the diff, the PR, or the logs.

## 5. Merge and watch the deploy

- [ ] Open the PR `develop` → `main`. Merge with a **merge commit**, not squash, so
      `develop` and `main` don't diverge.
- [ ] Railway: the pre-deploy step (`python manage.py migrate --no-input`) shows as
      succeeded in the deploy logs **before** the new container starts. A failed
      pre-deploy leaves the previous version serving, which is the safe outcome.
- [ ] Railway: the new container is healthy and `collectstatic` ran.
- [ ] Cloudflare: the Workers Build for the merge commit succeeded.
- [ ] If the release changes how the service starts or migrates, confirm on the
      **first** deploy that pre-deploy really ran (logs show migrations applied or
      "No migrations to apply"), because Railway passes commands through the image's
      `ENTRYPOINT`.

## 6. Smoke test production

- [ ] Frontend loads, and the language switcher and sidebar render.
- [ ] Start a chat as an anonymous user: the answer streams and cites sources.
- [ ] Sign in, and open the profile page.
- [ ] `/resources` and `/representatives` load.
- [ ] Browser console and Railway logs show no new errors for a few minutes.
- [ ] Run any post-deploy data steps from section 3, then `just db-status` against
      production to confirm chunk counts.

## 7. Close out

- [ ] Tag the release: `git tag -a vYYYY.MM.DD -m "<summary>" && git push --tags`
      (there are no tags yet; date-based tags need no version bump).
- [ ] Optionally create a GitHub release from the tag, using the PR body as notes.
- [ ] Merge `main` back into `develop` if the merge commit made them diverge.
- [ ] Delete merged feature branches and stale worktrees.

## Rolling back

- **App code:** redeploy the previous deployment from the Railway dashboard. This
  works as long as the schema is still compatible (section 3).
- **Schema:** reverse migrations are not always safe or even defined. Restore from
  the backup in section 3 rather than improvising, and note the incident in the
  PR.
- **Frontend:** roll back to the previous version from the Cloudflare Workers
  dashboard.
