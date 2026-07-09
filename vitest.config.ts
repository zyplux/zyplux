import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      enabled: true,
      exclude: ['apps/cz/src/index.ts'],
      include: ['apps/cz/src/**', 'packages/util-ts/src/**', 'packages/eslint-config/src/**'],
      provider: 'istanbul',
      thresholds: {
        branches: 90,
        functions: 90,
        lines: 90,
        statements: 90,
      },
    },
    isolate: false,
    projects: ['tests/eslint-config', 'tests/cz', 'tests/util-ts'],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
});
