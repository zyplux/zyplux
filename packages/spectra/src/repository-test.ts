import { setTimeout as sleep } from 'node:timers/promises';

import type { RepositoryFake } from './fakes/repository-fake.ts';

import { createRepositoryFake } from './fakes/repository-fake.ts';
import { cliTest } from './library-test-api.ts';

export const repositoryTest = cliTest
  .extend('sleep', () => sleep)
  .extend<{ repo: RepositoryFake }>({
    repo: async ({ shell, tempDir }, use) => {
      await use(createRepositoryFake(shell, tempDir.path));
    },
  });
