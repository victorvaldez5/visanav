# Releasing VisaNav

A release merges `develop` into `main` (a merge commit, no PR) and tags it
`vYYYY.MM.DD`. Pushing `main` deploys it: Cloudflare builds the frontend, Railway
deploys the API (migrations run as its pre-deploy step). The scheduled ingestion
service (`visanav-ingest`) rebuilds from the same push and, on its next hourly
run, ingests curated `data/` if the release changed it.

```bash
just release-check   # commits, migrations, new env vars, CI status (--local to run checks here)
just release         # check CI, confirm, merge develop -> main, push, tag (-y skips the prompt)
```

`just release` refuses to run unless CI is green on develop (or `--local` checks
pass), merges in a throwaway worktree so your checkout is untouched, and pushes
`main` and the tag atomically. It needs direct-push rights on `main`.

By hand, before releasing: set any new env vars it listed, and take a Railway
Postgres backup if a migration is marked `REVIEW`.

After releasing: Railway's pre-deploy migrate succeeded and the new container is
healthy, the Cloudflare build succeeded, and a smoke test passes (site loads, an
anonymous chat streams an answer, sign-in works).

**Knowledge base.** Within about an hour, `visanav-ingest` should show a
successful run in Railway; `python manage.py corpus_status` lists each corpus's
last ingestion. Two cases need you:

- A release that changes how pages are **extracted or chunked** (anything under
  `api/knowledge/` that alters chunk text) does not re-ingest scraped sources by
  itself, because their feeds have not changed. Run
  `python manage.py ingest_scrape --from-r2 --upsert` in the ingest service
  (curated `data/` re-ingests automatically, since its chunks change).
- If an ingest run fails with "below the ... floor", a corpus shrank by more than
  30% and was deliberately not replaced. Check why before rerunning with `--force`.

If the ingest service runs once before the API's pre-deploy migration finishes, it
fails that run and succeeds on the next; no action needed.

**Rollback:** redeploy the previous deployment in Railway (or Cloudflare for the
frontend). If a migration was destructive, restore the backup instead.
