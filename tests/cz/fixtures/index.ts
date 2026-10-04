import type { CliRunner } from '@zyplux/tests-fixtures/cli';

import { cliTest, makeFixture } from '@zyplux/tests-fixtures/story';
import { setTimeout as sleep } from 'node:timers/promises';

import type { Catalog, PublishedPackage, TsconfigPresets } from './act.ts';
import type {
  InitRepo,
  LiveWorkspace,
  Registries,
  Release,
  Repo,
  SeededTargets,
  UpgradeWorkspace,
  WriteArtifacts,
} from './arrange.ts';

import { createCatalog, createCz, createPackagedCz, loadPublishedPackages, loadTsconfigPresets } from './act.ts';
import {
  createInitRepo,
  createLiveWorkspace,
  createRegistries,
  createRelease,
  createRepo,
  createUpgradeWorkspace,
  createWriteArtifacts,
  enterCwd,
  seedReleaseTargets,
} from './arrange.ts';
import { expectNpmPackAndPublish } from './assert.ts';

type CzFixtures = {
  catalog: Catalog;
  cz: CliRunner;
  liveWorkspace: LiveWorkspace;
  packagedCz: CliRunner;
  publishedPackages: PublishedPackage[];
  registries: Registries;
  release: Release;
  repo: Repo;
  sleep: typeof sleep;
  tsconfigPresets: TsconfigPresets;
  upgradeWorkspace: UpgradeWorkspace;
};

export const test = cliTest.extend<CzFixtures>({
  catalog: async ({ cz, logs, network, tempDir }, use) => {
    await use(createCatalog(cz, tempDir, logs, network));
  },
  cz: async ({}, use) => {
    await use(createCz());
  },
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  packagedCz: async ({ tempDir }, use) => {
    await use(await createPackagedCz(tempDir));
  },
  publishedPackages: async ({}, use) => {
    await use(loadPublishedPackages());
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
  sleep: makeFixture(sleep),
  tsconfigPresets: async ({}, use) => {
    await use(loadTsconfigPresets());
  },
  upgradeWorkspace: async ({ network, tempDir }, use) => {
    await use(createUpgradeWorkspace(network, tempDir));
  },
});

export const targetsTest = test.extend<{
  expectNpmPackAndPublish: typeof expectNpmPackAndPublish;
  targets: SeededTargets;
}>({
  expectNpmPackAndPublish: makeFixture(expectNpmPackAndPublish),
  targets: [
    async ({ repo, tempDir }, use) => {
      repo.setRoot(tempDir.path);
      await use(await seedReleaseTargets(tempDir));
    },
    { auto: true },
  ],
});

export const tempCwdTest = test.extend<{ initRepo: InitRepo; tempCwd: undefined; writeArtifacts: WriteArtifacts }>({
  initRepo: async ({ tempDir }, use) => {
    await use(createInitRepo(tempDir));
  },
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
  writeArtifacts: async ({ tempDir }, use) => {
    await use(createWriteArtifacts(tempDir));
  },
});

export type { Catalog } from './act.ts';
export type { TempDir } from '@zyplux/tests-fixtures/fs';
export { describe, expect } from 'vitest';
