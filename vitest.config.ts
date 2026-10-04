import { JournaldReporter } from '@zyplux/spectra/reporters/journald-reporter';
import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      enabled: true,
      exclude: ['apps/cz/src/index.ts'],
      include: [
        'apps/cz/src/**',
        'packages/util-ts/src/**',
        'packages/eslint-config/src/**',
        'packages/spectra/src/**',
      ],
      provider: 'istanbul',
      thresholds: {
        branches: 90,
        functions: 90,
        lines: 90,
        statements: 90,
      },
    },
    isolate: false,
    projects: ['tests/eslint-config', 'tests/cz', 'tests/util-ts', 'tests/spectra'],
    reporters: [...configDefaults.reporters, new JournaldReporter({ identifier: 'zyplux' })],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
});
