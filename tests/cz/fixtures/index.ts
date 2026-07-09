import type { CliRunner } from '@zyplux/tests-fixtures';

import { cliTest } from '@zyplux/tests-fixtures';

import type { Catalog } from './act';
import type { LiveWorkspace, Registries, Release, Repo, SeededTargets } from './arrange';

import { createCatalog, createCz } from './act';
import {
  createLiveWorkspace,
  createRegistries,
  createRelease,
  createRepo,
  enterCwd,
  seedReleaseTargets,
} from './arrange';

type CzFixtures = {
  catalog: Catalog;
  cz: CliRunner;
  liveWorkspace: LiveWorkspace;
  registries: Registries;
  release: Release;
  repo: Repo;
};

export const test = cliTest.extend<CzFixtures>({
  catalog: async ({ cz, logs, tempDir }, use) => {
    await use(createCatalog(cz, tempDir, logs));
  },
  cz: async ({}, use) => {
    await use(createCz());
  },
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  registries: async ({ network }, use) => {
    await use(createRegistries(network));
  },
  release: async ({ registries, repo, shell }, use) => {
    await use(createRelease(repo, registries, shell));
  },
  repo: async ({ shell, tempDir }, use) => {
    await use(createRepo(shell, tempDir));
  },
});

export const targetsTest = test.extend<{ targets: SeededTargets }>({
  targets: [
    async ({ repo, tempDir }, use) => {
      repo.setRoot(tempDir.path);
      await use(await seedReleaseTargets(tempDir));
    },
    { auto: true },
  ],
});

export const tempCwdTest = test.extend<{ tempCwd: undefined }>({
  tempCwd: [
    async ({ tempDir }, use) => {
      const restoreCwd = enterCwd(tempDir.path);
      try {
        await use(undefined);
      } finally {
        restoreCwd();
      }
    },
    { auto: true },
  ],
});

export type { TempDir } from '@zyplux/tests-fixtures';
export { describe, expect } from 'vitest';
