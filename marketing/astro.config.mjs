// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";

// Static output (the default). Deployed to Cloudflare as static assets on
// www.visanav.org — the chat SPA (app.visanav.org) and Django API
// (api.visanav.org) are separate surfaces.
//
// i18n: English keeps its bare URLs (no redirects, existing backlinks and sitemap
// stay valid) and Spanish lives under /es/. The locale list mirrors
// /i18n/supported-locales.json (CI: scripts/check_i18n_parity.mjs); see
// src/i18n/index.ts and docs/i18n-architecture.md.
export default defineConfig({
  site: "https://www.visanav.org",
  // Pages are served at /directory/ (directory/index.html); the slashless form
  // redirects. "always" keeps dev, links, canonical and the sitemap on one form.
  trailingSlash: "always",
  i18n: {
    defaultLocale: "en",
    locales: ["en", "es"],
    routing: { prefixDefaultLocale: false },
  },
  integrations: [
    sitemap({
      // Emits <xhtml:link rel="alternate" hreflang> between a page and its /es/
      // twin. Pages with no translation (terms, privacy) get no alternates.
      i18n: { defaultLocale: "en", locales: { en: "en", es: "es" } },
      filter: (page) => !page.endsWith("/404/"),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
