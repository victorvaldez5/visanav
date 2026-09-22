# Contributing to VisaNav

Thanks for helping build a free, trustworthy immigration tool. There are two
very different ways to contribute, and you do **not** need to be a programmer to
do the most valuable one.

- **Add or improve country data** — plain-language immigration knowledge and
  directories of free/low-cost legal help. This is the community-facing work and
  the biggest way to help. **Start here → [data/CONTRIBUTING-data.md](data/CONTRIBUTING-data.md).**
- **Work on the code** — the Django API, the Vue frontend, or the scraper. See
  [README.md](README.md) for local setup and [CLAUDE.md](CLAUDE.md) for the
  architecture.

Everyone participating agrees to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Contributing data (the short version)

The full walkthrough lives in
[data/CONTRIBUTING-data.md](data/CONTRIBUTING-data.md), but the shape of it:

1. Country data lives under `data/countries/<cc>/` (`<cc>` is the lowercase
   [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) code).
   Copy `data/countries/_template/` to start a new country.
2. **Knowledge** is Markdown with YAML frontmatter under `knowledge/`.
   **Resources** are YAML lists under `resources/`.
3. Follow the golden rules: cite a real `source_url`, prefer official sources
   (anything marked `source_type: official` must link to a domain listed in that
   country's `meta.yaml`), give no case-specific legal advice, summarize rather
   than paste, and set `last_verified` to the day you checked.
4. Validate before opening a PR:
   ```bash
   pip install -r data/scripts/requirements.txt
   python data/scripts/validate.py
   ```

CI runs the same validator on every `data/` PR, but that only checks **format**.
A human maintainer still reviews whether the facts are right and the sources are
good. Not sure where to start? Open a
[**New country data**](https://github.com/victorvaldez5/visanav/issues/new/choose)
issue.

## Contributing code

1. Set up a local environment following the [README](README.md) (Docker Compose
   is the primary workflow).
2. Before opening a PR, run the checks for whatever you touched:
   - API: `poetry run pytest` and `poetry run ruff check .` (in `api/`).
   - Frontend: `npm run lint` and `npm run build` (in `frontend/`).
   - Scraper: `pytest` (in `scrapers/uscis_scraper/`).
3. CI (`.github/workflows/`) runs these on every PR; green CI is required to merge.

## Pull request conventions

- **Keep PRs focused.** One logical change per PR is much easier to review.
- **Conventional Commit titles.** Use `type(scope): summary`, e.g.
  `feat(frontend): add language switcher` or `fix(api): handle empty query`.
  Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- **Fill in the PR template** and link any related issue.

## Sign your commits (DCO)

VisaNav uses the [Developer Certificate of Origin](https://developercertificate.org/)
(DCO). Every commit must be signed off, which certifies that you wrote the
contribution (or otherwise have the right to submit it) and that it may be
distributed under the project's licenses.

Add the sign-off automatically with `-s`:

```bash
git commit -s -m "feat(data): add naturalization basics for Canada"
```

This appends a line to your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

The name and email must be real and match your Git identity. If you forgot on
your last commit, run `git commit --amend -s`; for several commits, rebase and
sign them off.

## Licensing of contributions

VisaNav is deliberately split into two licenses, and your contribution is
accepted under whichever applies:

- **Code** (everything outside `data/`) is licensed under
  **[AGPL-3.0](LICENSE)**. Code contributions are accepted under the same terms.
- **Data** (the `data/` corpus: knowledge and resources) is licensed under
  **[Creative Commons Attribution 4.0 International (CC-BY-4.0)](data/LICENSE)**
  so it can be reused as widely as possible with attribution. Data contributions
  are accepted under those terms.

By signing off your commit (DCO) you confirm you have the right to contribute the
work under the applicable license.

## Reporting problems

- **Bugs and feature ideas:** open an issue using the
  [templates](https://github.com/victorvaldez5/visanav/issues/new/choose).
- **Security vulnerabilities:** do **not** open a public issue. Follow
  [SECURITY.md](SECURITY.md).
- **Conduct concerns:** see the [Code of Conduct](CODE_OF_CONDUCT.md).
