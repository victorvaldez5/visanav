# /i18n

Shared internationalization assets that are not owned by any single deployed
surface. See [`docs/i18n-architecture.md`](../docs/i18n-architecture.md) for the
full design.

## Contents

- [`supported-locales.json`](./supported-locales.json): the canonical locale
  allowlist. This is the single source of truth for which locales exist. Each
  surface declares its own list in its own idiom:
  - Django `LANGUAGES` in `api/api_project/base.py`
  - `SUPPORTED_LOCALES` in `frontend/src/i18n/index.ts`
  - Astro `i18n.locales` in `marketing/astro.config.mjs` (added in the marketing
    phase)

  CI ([`scripts/check_i18n_parity.mjs`](../scripts/check_i18n_parity.mjs)) fails if
  any surface's list drifts from `supported-locales.json`.

- [`GLOSSARY.md`](./GLOSSARY.md): canonical translations for domain terms, so every
  surface renders "green card", "asylum", "petitioner", etc. identically.

## Adding a locale

1. Add it to `supported-locales.json` (move it out of `planned` into `locales`).
2. Add it to each surface's declared list (Django `LANGUAGES`, the Vue
   `SUPPORTED_LOCALES`, Astro `i18n.locales`).
3. Provide the catalog file for that locale on each surface.
4. Only reveal it in a surface's language switcher once that surface is fully
   translated and reviewed (the launch gate). English fallback covers gaps in the
   meantime.

## Translation workflow

Machine-first (Claude generates the first pass) → contributor (community refines via
PR) → human review before a locale is revealed. Start every translation from
`GLOSSARY.md`.
