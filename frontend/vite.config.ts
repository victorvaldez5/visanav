import path from 'node:path'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
// @ts-expect-error - No types for vite-plugin-eslint
import eslint from 'vite-plugin-eslint'

// https://vite.dev/config/
export default defineConfig({
    plugins: [vue(), tailwindcss(), eslint()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        }
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://api:8000',
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
})
