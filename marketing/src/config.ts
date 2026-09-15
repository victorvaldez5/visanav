// Public runtime config. `PUBLIC_`-prefixed vars are inlined into client code by
// Vite at build time; defaults target production so the site builds with no .env.
// Override in marketing/.env for local dev (e.g. point at localhost:8000 / :3000).

export const SITE_URL = "https://www.visanav.org";
export const APP_URL = import.meta.env.PUBLIC_APP_URL ?? "https://app.visanav.org";
export const API_URL = import.meta.env.PUBLIC_API_URL ?? "https://api.visanav.org";

// Cloudflare Turnstile site key (public). Defaults to Cloudflare's always-pass
// TEST key so the widget renders out of the box — set the real key via
// PUBLIC_TURNSTILE_SITE_KEY in prod, paired with TURNSTILE_SECRET_KEY on the API.
export const TURNSTILE_SITE_KEY =
  import.meta.env.PUBLIC_TURNSTILE_SITE_KEY ?? "1x00000000000000000000AA";

/** Deep-link into the chat app for a specific directory org (no account needed). */
export const orgAppLink = (id: string) => `${APP_URL}/?org=${encodeURIComponent(id)}`;

export const SUBMISSIONS_ENDPOINT = `${API_URL}/api/network/submissions/`;
