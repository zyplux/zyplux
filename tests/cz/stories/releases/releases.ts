import { makeFixture } from '@zyplux/spectra/library-test-api';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { czTest } from '#cli-test';

import type { ActionRelease } from './action-release.ts';
import type { LiveWorkspace, NpmTarget, Registries, Release, SeededTargets } from './release-scenario.ts';

import { createActionRelease } from './action-release.ts';
import { createNotesCapture, expectGithubRelease, expectNpmPackAndPublish } from './publish-assertions.ts';
import { createPreparation } from './release-preparation.ts';
import {
  createLiveWorkspace,
  createNpmTarget,
  createRegistries,
  createRelease,
  seedReleaseTargets,
} from './release-scenario.ts';
export const test = czTest.extend<{
  actionRelease: ActionRelease;
  expectGithubRelease: typeof expectGithubRelease;
  expectNpmPackAndPublish: typeof expectNpmPackAndPublish;
  liveWorkspace: LiveWorkspace;
  loadArtifact: (relativePath: string) => Promise<string>;
  npmTarget: NpmTarget;
  prepareWorkspace: () => Promise<void>;
  registries: Registries;
  release: Release;
  releaseNotes: ReturnType<typeof createNotesCapture>;
  targets: SeededTargets;
}>({
  actionRelease: async ({ repo, shell, tempDir }, use) => {
    await use(await createActionRelease({ repo, shell, tempDir }));
  },
  expectGithubRelease: makeFixture(expectGithubRelease),
  expectNpmPackAndPublish: makeFixture(expectNpmPackAndPublish),
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  loadArtifact: async ({ tempDir }, use) => {
    await use(async relativePath => readFile(path.join(tempDir.path, relativePath), 'utf8'));
  },
  npmTarget: async ({ shell, tempDir }, use) => {
    await use(createNpmTarget(shell, tempDir));
  },
  prepareWorkspace: async ({ liveWorkspace, shell, tempDir }, use) => {
    await use(async () => createPreparation({ root: liveWorkspace.root, shell, tempDir }));
  },
  registries: async ({ network }, use) => {
    await use(createRegistries(network));
  },
  release: async ({ registries, repo, shell }, use) => {
    await use(createRelease(repo, registries, shell));
  },
  releaseNotes: async ({ shell }, use) => {
    await use(createNotesCapture(shell));
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
