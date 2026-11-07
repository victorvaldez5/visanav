# Working on VisaNav

Branch from `develop` and open the pull request against `develop`. One logical change per branch. Title it in [Conventional Commits](https://www.conventionalcommits.org/) form, as [CONTRIBUTING.md](CONTRIBUTING.md) describes.

`main` is production. It changes only when `just release` merges `develop` and tags `vYYYY.MM.DD` ([docs/RELEASING.md](docs/RELEASING.md)). Do not open or merge a pull request into `main`. CI rejects that pull request (`scripts/check_pr_base.sh`). The GitHub default branch stays `main` because Railway follows it.

Before pushing, run the checks for what you touched. [CONTRIBUTING.md](CONTRIBUTING.md) lists them. `just test` runs every suite. These need no production keys once `config/.env.example` has been copied to `config/.env`:

- **Data:** `just validate-data`
- **API:** `just test-api` and `just lint` (`just test-api` needs local Postgres from `just db` only)
- **Frontend** (in `frontend/`): `npm run lint` and `npm run build`
- **Scraper:** `just test-scraper`
- **Translations:** `just check-i18n`

CI (`.github/workflows/ci.yml`) runs the same suites for the paths that changed. The aggregate job is `ci`. Merge to `develop` only when that job is green.

Ship with `just release-check`, then `just release`. That push to `main` deploys. Do not deploy, apply Railway config, or run the manual scrape workflow as part of an ordinary change.
