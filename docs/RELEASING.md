# Releasing VisaNav

A release is a `develop` → `main` merge PR. Merging ships it: Cloudflare builds
the frontend, Railway deploys the API (migrations run as its pre-deploy step).

Before merging:

- [ ] CI is green on `develop` (or run `just lint`, `just test`, `just check-i18n` locally).
- [ ] Skim `git log --oneline --no-merges origin/main..develop`: all of it should ship now.
- [ ] Migrations: `git diff --name-only origin/main...develop | grep migrations/`.
      If any are destructive or irreversible, take a Railway Postgres backup first.
- [ ] New env vars in `config/.env.example` are set on Railway / Cloudflare / GitHub.
- [ ] Any manual data step (for example `just corpus-ingest`) is noted in the PR.

Merge with a merge commit (not squash) so the branches don't diverge. Then:

- [ ] Railway deploy logs show the pre-deploy migrate succeeded and the new container is healthy.
- [ ] Cloudflare build succeeded.
- [ ] Smoke test: the site loads, an anonymous chat streams an answer, sign-in works.
- [ ] Tag it: `git tag -a vYYYY.MM.DD -m "<summary>" && git push --tags`.

**Rollback:** redeploy the previous deployment in Railway (or Cloudflare for the
frontend). If a migration was destructive, restore the backup instead.
