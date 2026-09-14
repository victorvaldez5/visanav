/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Absolute base URL of the Django API, INCLUDING the /api prefix.
   * Unset in dev (Vite proxies /api → http://api:8000); set in production
   * on Cloudflare Pages, e.g.
   * https://api-frosty-rain-5363-production.up.railway.app/api
   */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
