import type { ViteUserConfig } from 'vitest/config';

import { JournaldReporter } from '@zyplux/spectra/journald-reporter';
import { configDefaults } from 'vitest/config';

const journalReporter = new JournaldReporter({ identifier: 'zyplux' });

export default {
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
    reporters: [...configDefaults.reporters, journalReporter],
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
} satisfies ViteUserConfig;
