# marketing/ — VisaNav public site (www.visanav.org)

The **static** marketing + public-resources site. Separate from the chat app
(`frontend/` → app.visanav.org) and the API (`api/` → api.visanav.org). Built
with **Astro** and prerendered to static HTML so it's fully indexable — the
whole point of this surface is SEO and public trust, which a client-rendered SPA
can't deliver.

## Pages

- `/` — homepage (what VisaNav is, how it helps, trust framing).
- `/directory` — the public-resources directory: ~995 nonprofit & pro-bono
  orgs, rendered at build time (indexable) with a pure client-side filter
  (search / state / pro-bono). Each entry deep-links into the chat app.
- `/partners` — the moderated NGO "request to be included" form. Posts to the
  API; **nothing is auto-listed** — an admin reviews each submission at `/nimda/`.

## Develop

```bash
npm install
cp .env.example .env   # optional: point at local API/app
npm run dev            # http://localhost:4321
npm run build          # -> dist/
npm run preview        # serve the built dist/
```

## Config

Runtime URLs come from `src/config.ts`, overridable with `PUBLIC_`-prefixed env
vars (see `.env.example`). Defaults target production, so `npm run build` works
with no `.env`.

## Directory data

`src/data/organizations.json` is generated from the API fixtures
(`api/network/fixtures/ra-orgs.json` + `probono_clean.json`) — the same data the
DB import migration consumes. It's committed so the build never depends on the
API. Refresh it after the fixtures change:

```bash
npm run sync:directory   # node scripts/build-directory.mjs
```

## Deploy (Cloudflare)

```bash
npm run build
npx wrangler deploy      # uploads ./dist as static assets (see wrangler.jsonc)
```

## Notes

- The NGO form POSTs to `POST /api/network/submissions/`. In production the
  API's `CSRF_TRUSTED_ORIGINS` (reused as `CORS_ALLOWED_ORIGINS`) must include
  `https://www.visanav.org`, or the browser will block the cross-origin POST.
- **Cloudflare Turnstile** protects the form. `PUBLIC_TURNSTILE_SITE_KEY` (here)
  renders the widget; `TURNSTILE_SECRET_KEY` (on the API) verifies the token
  server-side — a client-only widget is trivially bypassed. Both default to
  Cloudflare's always-pass test keys, so the form works out of the box; set the
  real pair from the Turnstile dashboard in prod (widget domain must include
  `www.visanav.org`). If the API's secret is unset, verification is skipped.
- `public/og.png` is referenced for social previews but not yet added — drop a
  1200×630 image there when ready.
