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
    // DOM/jsdom is required. Tests that touch browser globals (localStorage) stub
    // them explicitly, which keeps the suite fast and dependency-light.
    environment: 'node',
    include: ['src/**/*.{test,spec}.ts', 'worker/**/*.{test,spec}.ts'],
    coverage: {
      provider: 'v8',
      // `text` prints a summary in CI logs; `lcov`/`html` write ./coverage for
      // local browsing and any external coverage upload.
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './coverage',
      // Scoped to the TS logic layer (composables, services, stores, lib). `.vue`
      // SFCs are excluded until component tests land — they need jsdom, and the
      // v8 provider can't parse an uncovered SFC's <template> as raw source.
      include: ['src/**/*.ts', 'worker/**/*.ts'],
      exclude: [
        'src/**/*.{test,spec}.ts',
        'worker/**/*.{test,spec}.ts',
        'src/**/*.d.ts',
        // Generated shadcn-style UI primitives — thin re-export/variant wrappers.
        'src/components/ui/**',
      ],
      // No failing thresholds yet — coverage is reported so it's visible and can
      // grow. Raise `thresholds` here once the baseline is established to gate PRs.
    },
  },
})
