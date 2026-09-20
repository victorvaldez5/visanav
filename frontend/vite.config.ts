import path from 'node:path'
import dns from 'node:dns/promises'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
// @ts-expect-error - No types for vite-plugin-eslint
import eslint from 'vite-plugin-eslint'

// Content-Security-Policy for the built app. It's the second layer behind the
// Markdown sanitizer (src/lib/sanitize.ts): even if a hostile assistant reply
// slipped script or a remote asset past the sanitizer, the browser refuses to
// run inline/foreign script and refuses to connect anywhere but our own API —
// so a poisoned reply can't beacon a conversation transcript out.
//   - script-src 'self'      no inline/eval; the Vite build emits only external
//                            module scripts and Vue ships precompiled (no eval).
//   - img-src 'self' data:   blocks the classic <img src=evil?data> exfil.
//   - connect-src            our API origins ONLY — fetch/XHR/SSE can't reach
//                            an attacker's host. UPDATE this list if the API
//                            origin changes (it's baked via VITE_API_BASE_URL).
//   - style-src 'unsafe-inline' is required for Vue's dynamic :style / scoped
//                            styles; style injection isn't the exfil threat here.
// Delivered as a <meta> injected into the built index.html rather than via
// public/_headers, because header support on Cloudflare's static-assets Worker
// is unverified — a meta tag ships with the document regardless. Injected only
// for `vite build`: adding it in dev would break Vite's HMR (inline script/eval).
const CONTENT_SECURITY_POLICY = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self' https://api.visanav.org https://api-frosty-rain-5363-production.up.railway.app",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
].join('; ')

function cspMeta() {
    return {
        name: 'inject-csp-meta',
        apply: 'build' as const,
        transformIndexHtml(html: string) {
            return {
                html,
                tags: [{
                    tag: 'meta',
                    attrs: {'http-equiv': 'Content-Security-Policy', content: CONTENT_SECURITY_POLICY},
                    injectTo: 'head-prepend' as const,
                }],
            }
        },
    }
}

// Where the dev server proxies `/api`. Under docker-compose the backend is the
// `api` service (resolvable on the compose network); running `vite` directly on
// a host, that name doesn't resolve, so fall back to the API's host-published
// port. Set $VITE_DEV_API_PROXY to override either way.
async function resolveApiTarget() {
    if (process.env.VITE_DEV_API_PROXY) return process.env.VITE_DEV_API_PROXY
    try {
        await dns.lookup('api')
        return 'http://api:8000'
    } catch {
        return 'http://localhost:8000'
    }
}

// https://vite.dev/config/
export default defineConfig(async ({command}) => ({
    // Run ESLint only during dev (`vite`/`command === 'serve'`). Linting during
    // production builds (`vite build`, e.g. on Cloudflare) just adds time and
    // noise to CI logs — use `npm run lint` (or lint:fix) for that instead.
    plugins: [vue(), tailwindcss(), cspMeta(), ...(command === 'serve' ? [eslint()] : [])],
    resolve: {
        alias: {
            '@': path.resolve(import.meta.dirname, './src'),
        }
    },
    server: {
        // Honor $PORT when set (e.g. a preview harness assigning a free port),
        // else default to 3000 — the port docker-compose maps and the API's
        // CORS/allowed-hosts expect.
        port: Number(process.env.PORT) || 3000,
        proxy: {
            '/api': {
                target: await resolveApiTarget(),
                changeOrigin: true,
                secure: false
            }
        },
        allowedHosts: [
            'localhost', '0.0.0.0', "127.0.0.1", "172.18.0.4"
        ],
        host: '0.0.0.0',
        cors: {
            origin: 'http://api:8000',
            methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'],
        }
    },
}))
