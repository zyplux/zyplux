import { runCz } from '@zyplux/cz/cli';
import { createCliRunner } from '@zyplux/spectra/cli-runner';
import { cliTest } from '@zyplux/spectra/library-test-api';
import { setTimeout as sleep } from 'node:timers/promises';

import type { Repo } from './repository-fake.ts';

import { createRepo } from './repository-fake.ts';

export const czTest = cliTest
  .extend('cz', () => createCliRunner(runCz))
  .extend('sleep', () => sleep)
  .extend<{ repo: Repo }>({
    repo: async ({ shell, tempDir }, use) => {
      await use(createRepo(shell, tempDir));
    },
  });
