import type { CliRunner } from '@zyplux/spectra/cli-runner';

import { runRelease } from '@zyplux/release/cli';
import { VersionFieldSchema, VersionFileSchema } from '@zyplux/release/contracts';
import { createCliRunner } from '@zyplux/spectra/cli-runner';
import { makeFixture } from '@zyplux/spectra/library-test-api';
import { parseJson } from '@zyplux/util/json';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { czTest } from '#cli-test';

import type { ActionRelease } from './action-release.ts';
import type { LiveWorkspace, NpmTarget, Registries, Release, SeededTargets } from './release-scenario.ts';

import { createActionRelease } from './action-release.ts';
import { createNotesCapture, expectGithubRelease, expectNpmPublish } from './publish-assertions.ts';
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
  expectNpmPublish: typeof expectNpmPublish;
  liveWorkspace: LiveWorkspace;
  loadActionOutputs: () => Promise<string>;
  loadArtifact: (relativePath: string) => Promise<string>;
  loadPackageVersion: (relativePath: string) => Promise<string>;
  nativeRelease: CliRunner;
  npmTarget: NpmTarget;
  prepareWorkspace: () => Promise<void>;
  registries: Registries;
  release: Release;
  releaseAssetPath: string;
  releaseNotes: ReturnType<typeof createNotesCapture>;
  targets: SeededTargets;
}>({
  actionRelease: async ({ repo, shell, tempDir }, use) => {
    await use(await createActionRelease({ repo, shell, tempDir }));
  },
  expectGithubRelease: makeFixture(expectGithubRelease),
  expectNpmPublish: makeFixture(expectNpmPublish),
  liveWorkspace: async ({}, use) => {
    await use(createLiveWorkspace());
  },
  loadActionOutputs: async ({ env, loadArtifact, tempDir }, use) => {
    env.set('GITHUB_OUTPUT', path.join(tempDir.path, 'outputs'));
    await use(async () => loadArtifact('outputs'));
  },
  loadArtifact: async ({ tempDir }, use) => {
    await use(async relativePath => readFile(path.join(tempDir.path, relativePath), 'utf8'));
  },
  loadPackageVersion: async ({ loadArtifact }, use) => {
    await use(async relativePath => {
      const manifest = parseJson(await loadArtifact(relativePath), VersionFileSchema);
      return VersionFieldSchema.parse(manifest['version']);
    });
  },
  nativeRelease: async ({}, use) => {
    await use(createCliRunner(runRelease));
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
  releaseAssetPath: async ({ tempDir }, use) => {
    await use(path.join(tempDir.path, 'release.json'));
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
