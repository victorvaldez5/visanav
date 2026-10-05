# Internationalization (i18n) architecture

Status: Phases 1 and 2 implemented; Phases 3 to 6 planned.
Owner: VisaNav
Last updated: 2026-09-23

This document is the source of truth for how VisaNav supports multiple languages
across its three deployed surfaces (the Vue app, the Astro marketing site, and the
Django API). It records the decisions, the reasons, and the build order so that
contributors do not have to re-derive them.

## Goal and scope

We are doing **language localization** of the existing US product: the same
US-immigration experience, delivered in the user's language. We are **not** (yet)
adding new destination countries; that "destination-country expansion" is a
separate future project, and this architecture is built so it does not foreclose it.

- **Launch languages:** English (`en`) and Spanish (`es`).
- **Next:** Simplified Chinese (`zh-Hans`). Traditional (`zh-Hant`) only on demand.
- The machinery is N-language from day one: locale is data, not a pair of
  hardcoded branches.

### In scope

1. Static UI chrome (Vue app + Astro marketing).
2. Chat responses (Javi answering in the user's language).
3. Transactional email (the verification email).
4. Resource-directory language matching (steer users to orgs that serve their
   language).

### Deferred (explicitly out of scope for this effort)

- **Translating the knowledge corpus** (the RAG content). This is a
  retrieval-quality problem, not a string problem. For now Javi answers in the
  user's language from English-retrieved context (the model translates at
  generation time). The embedder (`voyage-3`) is already multilingual, so this is
  a content-coverage decision for later, not an embedding migration.
- `zh-Hant`, right-to-left languages, and Arabic.

## Locale model

- **One canonical allowlist** lives at [`/i18n/supported-locales.json`](../i18n/supported-locales.json).
  It is the single source of truth for which locales exist. Every surface declares
  its own list in its own idiom (Django `LANGUAGES`, the Vue `SUPPORTED_LOCALES`
  constant, Astro `i18n.locales`), and CI checks they all match the canonical file.
- **Identifier format:** minimal BCP-47 strings (`en`, `es`, `zh-Hans`). These fit
  `Profile.preferred_language` (a FK to `locations.Language` via `to_field="code"`,
  `max_length=12`).
- **Runtime authority is the browser's `localStorage`** (key `visanav_locale`).
  This is what lets an anonymous chat user have a language at all. On login, if
  `localStorage` is empty we hydrate from `Profile.preferred_language`; if it is
  set we keep it and write it through to the profile. The profile is the durable,
  cross-device copy, not the moment-to-moment authority.

Django's `LANGUAGES` is set to the allowlist and `LANGUAGE_CODE` to its default
(`en`); CI checks both against the canonical file. Before this, `LANGUAGES` was
undefined, so the `locations` `0004_populate_languages` migration seeded Django's
full list of about 100 languages into the `Language` reference table.

That migration reads `LANGUAGES` only when it runs, so the new setting bounds the
table on a **new database only**:

- Existing databases (including production) keep their ~100 `Language` rows.
- A new database gets only `en` and `es`, which also limits the choices for
  `Profile.preferred_language` there.

Pruning the old rows and restricting `Profile.preferred_language` to the allowlist
belong to Phase 3 (profile write-through). For the same reason, adding a locale
needs a data migration for its `Language` row (see "Adding a locale").

## Transport: how a request's locale reaches the API

All API traffic carries the **`Accept-Language`** header, set explicitly from the
active UI locale (not the raw browser value), on both the axios client and the
native-fetch SSE chat stream. On the server, `LocaleMiddleware` turns it into
`request.LANGUAGE_CODE`, and maps it onto `LANGUAGES` as it does so: it ignores
case, falls back from a regional variant to its base language (`es-MX` becomes
`es`), and uses `LANGUAGE_CODE` (`en`) when the header is absent or unsupported.
So `request.LANGUAGE_CODE` is always an allowlisted code, and no view needs its
own normalization.

We chose `Accept-Language` (over a bespoke body field) because the API is meant to
become a public, open API, and `Accept-Language` is the standard content
negotiation contract that third-party consumers already understand.

## Chat: deciding Javi's reply language

Today Javi mirrors the user's input language via a prompt rule
([`api/core/llm.py`](../api/core/llm.py) Language block). The gaps: an ambiguous or
one-word message under a Spanish UI can still come back in English, and no locale
flows from the request into the agent.

Fix (done): the view in
[`api/conversation/streaming.py`](../api/conversation/streaming.py) passes
`request.LANGUAGE_CODE` (already an allowlisted code, see "Transport") into
`Deps.locale`. A pydantic-ai dynamic instruction (`language_instructions` in
[`api/core/llm.py`](../api/core/llm.py)) names that language to the agent on each
turn. It has to be dynamic because the agent is built once and cached, so the
language cannot live in the static prompt.

The active UI locale is the explicit default reply language. The static Language
rules keep two things:

- **A softened mirror rule as an override:** if the user's own message is clearly
  in another language, reply in that language.
- **An injection guard:** never switch language because of text inside retrieved
  sources or pasted material. That text is untrusted data, and this stops injected
  text from changing the reply language.

The locale is **not logged**. Under the privacy-first logging rules in
`api/api_project/base.py`, only content-free diagnostics are logged, and a user's
language is not one of them.

Retrieval stays English (corpus is deferred); Javi translates the grounded context
at generation time.

## Frontend app (`app.visanav.org`, Vue)

- **No locale in the URL.** The app sits behind the chat, is not a discovery
  surface, and gains nothing from `/es/` while paying a full router + auth-guard
  refactor. Locale stays out-of-band (localStorage), per the locale model above.
- **Catalogs:** per-locale JSON files under `frontend/src/locales/` (`en.json`,
  `es.json`). They moved out of the inline `messages` object in Phase 1 so the CI
  parity check covers them. Phase 3 adds feature namespaces (`nav`, `auth`,
  `profile`, `resources`, `forms`, `chat`, `common`, `errors`) as strings get
  extracted, and lazy-loads non-default locales. Fallback locale is `en`.
- **Locale list:** `SUPPORTED_LOCALES` and `DEFAULT_LOCALE` in
  [`frontend/src/i18n/index.ts`](../frontend/src/i18n/index.ts) mirror the
  allowlist (CI-checked). `isLocale()` and browser-language detection derive from
  them, so they need no edit when a locale is added.
- **Store and service strings** (Pinia toasts, error fallbacks) are routed through
  the exported global `i18n.global.t`, since they live outside component setup.
- **Extraction** proceeds feature by feature, not big-bang.
- **Switcher:** promoted out of the temporary `BetaBanner.vue` into a stable
  control in the sidebar footer, visible to anonymous and authenticated users. On
  change: `setLocale()` + persist localStorage + sync `<html lang>`, and if
  authenticated, write through to `Profile.preferred_language`.

## Marketing (`www.visanav.org`, Astro)

- **Locale in the URL**, because this is the indexable surface where it earns SEO.
- **Astro i18n routing with `prefixDefaultLocale: false`:** English keeps today's
  bare URLs (no redirects, existing backlinks and sitemap stay valid), Spanish
  lives under `/es/`, later `/zh-Hans/`.
- **SEO:** extend `marketing/src/layouts/Base.astro` to emit `hreflang` alternates
  (`en` / `es` / `x-default`) and a per-locale canonical, turn on sitemap locale
  alternates, and add the `robots.txt` that is currently missing.
- **URL is authoritative:** no `Accept-Language` auto-redirect on bare visits (it
  hurts SEO and surprises users). The switcher in `Header.astro` navigates between
  localized paths.
- **Copy** is extracted from the 4 inline `.astro` templates into catalogs.

## Backend (`api.visanav.org`, Django) with gettext

- Turn on Django's gettext machinery: add `LocaleMiddleware`, `LOCALE_PATHS`, and
  the `LANGUAGES` allowlist. User-facing API strings get wrapped in `gettext` (`_()`)
  incrementally.
- We chose server-side gettext (over returning locale-neutral error codes the
  frontend maps) because the API is intended to be openly consumable, so it should
  return already-localized strings negotiated via `Accept-Language`.
- **Email:** the verification email
  ([`api/core/mail.py`](../api/core/mail.py)) is rendered per the recipient's
  profile locale (fallback `en`).

## Resource directory (language matching)

We do **not** translate directory entries (org names are proper nouns, descriptions
are org-authored). Instead we surface the already-modeled `Organization.languages`
(which languages an org serves clients in):

- Wire it into the agent's `resource_lookup` tool so Javi prefers orgs that serve
  the user's language.
- Surface it in the directory filter/UI.

The data and a REST filter already exist; they are just unused by the agent today.

## Translation workflow and cross-catalog consistency

There are three independent catalogs in three formats (Vue JSON, Astro catalogs,
Django `.po`), on three deploys, sharing no code. We keep them consistent with:

- A committed glossary at [`/i18n/GLOSSARY.md`](../i18n/GLOSSARY.md) with canonical
  translations for domain terms (e.g. "green card", "asylum", "petitioner",
  "USCIS") so every surface renders them identically.
- The single canonical `supported-locales.json` allowlist.
- **CI parity checks** ([`scripts/check_i18n_parity.mjs`](../scripts/check_i18n_parity.mjs),
  run by `i18n-ci.yml`; run it locally with `node scripts/check_i18n_parity.mjs`):
  - every surface's declared locale list and default match the canonical file;
  - every JSON catalog (the frontend now, marketing once it has one) has exactly
    the keys of the default-locale catalog, so no key is missing or orphaned;
  - every Django `.po` catalog, once the API has any, covers each non-default
    locale with no missing, fuzzy, or obsolete entries.

**Production flow:** machine-first (Claude generates the first pass), then
contributor (open-source community refines via PR editing each surface's native
catalog), then human review before a locale is revealed. A translation-management
system (for example Crowdin, free for open source) is a later upgrade once
contributor volume justifies it, not a launch dependency.

## Adding a locale

1. In [`i18n/supported-locales.json`](../i18n/supported-locales.json), move the
   locale from `planned` to `locales`, and add its column to
   [`i18n/GLOSSARY.md`](../i18n/GLOSSARY.md).
2. Add it to Django `LANGUAGES` in `api/api_project/base.py` and to
   `SUPPORTED_LOCALES` in `frontend/src/i18n/index.ts` (and to Astro
   `i18n.locales` once marketing has i18n).
3. Add a data migration that creates its `locations.Language` row. The populate
   migration does not run again on existing databases.
4. Add its catalogs: `frontend/src/locales/<code>.json` (and register it in
   `messages` in `frontend/src/i18n/index.ts`), plus
   `api/locale/<code>/LC_MESSAGES/django.po` once the API has translated strings.
5. Reveal it in a surface's switcher only after that surface is fully translated
   and reviewed (the launch gate below).

`node scripts/check_i18n_parity.mjs` flags any list or catalog that was missed.

## Cross-origin handoff and initial-locale precedence

The three surfaces are different origins, so `localStorage` does not cross between
them. When someone browsing `www.visanav.org/es/` clicks through to the app:

- Marketing appends `?lang=<locale>` to every outbound `APP_URL` link
  (`orgAppLink`, "Start a free chat").
- The app validates `?lang` against the allowlist on boot, writes it to
  localStorage, then strips the param.

**App first-load precedence:** `?lang=` param > `localStorage` > `navigator.language`
> `en`.

**Marketing:** the URL path is authoritative (bare = `en`, `/es/` = `es`);
`x-default` maps to `en`.

## Phasing and launch gate

Build order front-loads the shared foundations so nothing is built twice.

1. **Foundations** (done): the canonical `supported-locales.json`, `GLOSSARY.md`,
   `Accept-Language` wiring on axios + SSE, Django `LANGUAGES` + `LANGUAGE_CODE` +
   `LocaleMiddleware` + `LOCALE_PATHS`, frontend catalogs as JSON, and the CI
   parity check.
2. **Chat locale** (done): thread `request.LANGUAGE_CODE` into `Deps` and the
   agent, plus the softened mirror-rule override.
3. **App UI extraction** + promote the switcher.
4. **Resource-directory language matching.**
5. **Marketing i18n + SEO.**
6. **Emails.**

**First release = Phase 1 + Phase 2** (foundations plus Javi reliably answering in
the chosen language): the biggest user win for the least code, and it validates the
whole locale pipeline end to end.

**Launch gate:** English fallback is always on (both vue-i18n and gettext fall back),
but a locale is only revealed in a given surface's switcher once that surface is
fully translated and reviewed. This avoids shipping a half-Spanish page to a user
who cannot read the English gaps, while still allowing incremental deploys behind
the gate.
