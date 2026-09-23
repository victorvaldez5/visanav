# Contributing to VisaNav

Thanks for helping build a free, trustworthy immigration tool. Pick the path that
fits you:

| I want to... | Go here |
|---|---|
| Add or fix immigration information or legal-help listings (no coding needed) | [data/README.md](data/README.md) |
| Suggest a website, report wrong info, or volunteer to review, without editing files | [Improve the data](https://github.com/victorvaldez5/visanav/issues/new?template=improve_data.yml) issue |
| Add a scraper for a new source or country | [scrapers/README.md](scrapers/README.md) |
| Work on the app (API, frontend) | [README.md](README.md) for setup, [CLAUDE.md](CLAUDE.md) for architecture |
| Report a bug or suggest a feature | [Open an issue](https://github.com/victorvaldez5/visanav/issues/new/choose) |

## Before you open a pull request

Run the checks for whatever you touched (CI runs them too, and must be green to
merge):

- **Data:** `python data/scripts/validate.py`
- **API** (in `api/`): `poetry run pytest` and `poetry run ruff check .`
- **Frontend** (in `frontend/`): `npm run lint` and `npm run build`
- **Scraper** (in `scrapers/uscis_scraper/`): `pytest`
- **Translations** (locale lists, catalogs, `i18n/`): `node scripts/check_i18n_parity.mjs`.
  See [docs/i18n-architecture.md](docs/i18n-architecture.md), including "Adding a locale".

Keep each PR to one logical change, and title it in
[Conventional Commits](https://www.conventionalcommits.org/) style, e.g.
`feat(frontend): add language switcher` or `fix(data): update I-130 fee`.

## The fine print

- **Licensing:** code is [AGPL-3.0](LICENSE) and everything in `data/` is
  [CC-BY-4.0](data/LICENSE). By contributing, you agree your contribution is
  published under the license for the part you changed.
- **Conduct:** everyone participating follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- **Security issues:** never file them publicly. See [SECURITY.md](SECURITY.md).
