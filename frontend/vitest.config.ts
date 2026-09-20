import path from 'node:path'
import { defineConfig } from 'vitest/config'

// Vitest config kept separate from vite.config.ts so the dev server's ESLint
// plugin and proxy don't load during tests. The `@` alias mirrors vite.config.
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  test: {
    // The scrubber is pure and the composable only needs Vue's reactivity, so no
    // DOM/jsdom is required.
    environment: 'node',
    include: ['src/**/*.{test,spec}.ts'],
  },
})
