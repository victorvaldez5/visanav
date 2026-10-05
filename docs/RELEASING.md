# Releasing VisaNav

A release merges `develop` into `main` (a merge commit, no PR) and tags it
`vYYYY.MM.DD`. Pushing `main` deploys it: Cloudflare builds the frontend, Railway
deploys the API (migrations run as its pre-deploy step).

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

**Rollback:** redeploy the previous deployment in Railway (or Cloudflare for the
frontend). If a migration was destructive, restore the backup instead.
