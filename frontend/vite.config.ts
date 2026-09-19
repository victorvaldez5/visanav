import path from 'node:path'
import dns from 'node:dns/promises'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
// @ts-expect-error - No types for vite-plugin-eslint
import eslint from 'vite-plugin-eslint'

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
    plugins: [vue(), tailwindcss(), ...(command === 'serve' ? [eslint()] : [])],
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
