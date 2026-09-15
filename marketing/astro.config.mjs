// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";

// Static output (the default). Deployed to Cloudflare as static assets on
// www.visanav.org — the chat SPA (app.visanav.org) and Django API
// (api.visanav.org) are separate surfaces.
export default defineConfig({
  site: "https://www.visanav.org",
  integrations: [sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
