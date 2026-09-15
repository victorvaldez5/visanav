// Cloudflare Turnstile loader for the SPA. The site key is public and inlined at
// build time; it defaults to Cloudflare's always-pass TEST key so the widget
// renders with no config. Set the real key via VITE_TURNSTILE_SITE_KEY in prod,
// paired with TURNSTILE_SECRET_KEY on the API (which verifies the token — a
// client-only widget is trivially bypassed).
export const TURNSTILE_SITE_KEY =
    import.meta.env.VITE_TURNSTILE_SITE_KEY || "1x00000000000000000000AA";

const SCRIPT_SRC =
    "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

declare global {
    interface Window {
        turnstile?: {
            render: (el: HTMLElement, opts: Record<string, unknown>) => string;
            reset: (id?: string) => void;
            remove: (id?: string) => void;
        };
    }
}

let scriptPromise: Promise<void> | null = null;

/** Injects the Turnstile script once; resolves when window.turnstile is ready. */
export function loadTurnstile(): Promise<void> {
    if (window.turnstile) return Promise.resolve();
    if (scriptPromise) return scriptPromise;
    scriptPromise = new Promise<void>((resolve, reject) => {
        const s = document.createElement("script");
        s.src = SCRIPT_SRC;
        s.async = true;
        s.defer = true;
        s.onload = () => resolve();
        s.onerror = () => {
            scriptPromise = null; // allow a later retry
            reject(new Error("Failed to load Turnstile"));
        };
        document.head.appendChild(s);
    });
    return scriptPromise;
}
