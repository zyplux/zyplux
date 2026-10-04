import { makeFixture } from '@zyplux/spectra/library-test-api';

import { czTest } from '#cli-test';

import type { LiveWorkspace, Registries, Release, SeededTargets } from './release-scenario.ts';

import { expectNpmPackAndPublish } from './publish-assertions.ts';
import { createLiveWorkspace, createRegistries, createRelease, seedReleaseTargets } from './release-scenario.ts';
export const test = czTest.extend<{
  expectNpmPackAndPublish: typeof expectNpmPackAndPublish;
  liveWorkspace: LiveWorkspace;
  registries: Registries;
  release: Release;
  targets: SeededTargets;
}>({
  expectNpmPackAndPublish: makeFixture(expectNpmPackAndPublish),
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  registries: async ({ network }, use) => {
    await use(createRegistries(network));
  },
  release: async ({ registries, repo, shell }, use) => {
    await use(createRelease(repo, registries, shell));
  },
  targets: [
    async ({ repo, tempDir }, use) => {
      repo.setRoot(tempDir.path);
      await use(await seedReleaseTargets(tempDir));
    },
    { auto: true },
  ],
});
export { describe, expect } from 'vitest';
