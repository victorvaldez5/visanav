# Releasing VisaNav

A release is a `develop` → `main` merge PR. Merging ships it: Cloudflare builds
the frontend, Railway deploys the API (migrations run as its pre-deploy step).

```bash
just release-check   # commits, migrations, new env vars, CI status (--local to run checks here)
just release-pr      # open the develop -> main PR with a generated description
# merge it (merge commit, not squash), then watch the Railway and Cloudflare deploys
just release-tag     # tag origin/main as vYYYY.MM.DD
```

By hand, before merging: set any new env vars it listed, and take a Railway
Postgres backup if a migration is marked `REVIEW`.

After merging: Railway's pre-deploy migrate succeeded and the new container is
healthy, the Cloudflare build succeeded, and a smoke test passes (site loads, an
anonymous chat streams an answer, sign-in works).

**Rollback:** redeploy the previous deployment in Railway (or Cloudflare for the
frontend). If a migration was destructive, restore the backup instead.
