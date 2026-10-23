import type { ReleaseBatch } from '@zyplux/airlock/contracts';

import { runAirlock } from '@zyplux/airlock/cli';
import { ReleasePlanSchema, VersionFieldSchema, VersionFileSchema } from '@zyplux/airlock/contracts';
import { createCliRunner } from '@zyplux/spectra/cli-runner';
import { makeFixture } from '@zyplux/spectra/library-test-api';
import { repositoryTest } from '@zyplux/spectra/repository-test';
import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { readFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { ActionRelease } from './action-release.ts';
import type { LiveWorkspace, NpmTarget, Registries, Release, SeededTargets } from './release-scenario.ts';

import { createActionRelease } from './action-release.ts';
import { createContainerPublication } from './container-publication.ts';
import { createBundledConsumer, createDependencyWorkspace } from './npm-dependencies.ts';
import { createNotesCapture, expectGithubRelease, expectNpmPublish, expectPypiPublish } from './publish-assertions.ts';
import { createPreparation } from './release-preparation.ts';
import {
  createLiveWorkspace,
  createNpmTarget,
  createRegistries,
  createRelease,
  seedReleaseTargets,
} from './release-scenario.ts';
import { extendSurfaceChecks } from './surface-check.ts';

const releaseTest = repositoryTest
  .extend('airlock', () => createCliRunner(runAirlock))
  .extend<{
    actionRelease: ActionRelease;
    configureTarget: (kind: string, fields: string) => Promise<void>;
    consumer: SeededTargets['util'];
    containerRelease: { batch: ReleaseBatch; readManifest: () => string };
    expectGithubRelease: typeof expectGithubRelease;
    expectNpmPublish: typeof expectNpmPublish;
    expectPypiPublish: typeof expectPypiPublish;
    liveWorkspace: LiveWorkspace;
    loadActionOutputs: () => Promise<string>;
    loadArtifact: (relativePath: string) => Promise<string>;
    loadPackageVersion: (relativePath: string) => Promise<string>;
    npmTarget: NpmTarget;
    planReleases: (tag?: string) => Promise<ReleaseBatch[]>;
    prepareWorkspace: () => Promise<void>;
    registries: Registries;
    release: Release;
    releaseAssetPath: string;
    releaseNotes: ReturnType<typeof createNotesCapture>;
    targets: SeededTargets;
  }>({
    actionRelease: async ({ repo, shell, targets, tempDir }, use) => {
      await use(await createActionRelease({ repo, shell, targets, tempDir }));
    },
    configureTarget: async ({ targets }, use) => {
      await use(targets.configureTarget);
    },
    consumer: async ({ loadArtifact, shell, targets, tempDir }, use) => {
      await use(await createDependencyWorkspace({ loadArtifact, shell, targets, tempDir }));
    },
    containerRelease: async ({ configureTarget, env, planReleases, registries, repo, shell }, use) => {
      await configureTarget(
        'ghcr',
        'artifact_command = ["uv", "run", "--no-sync", "python", "-m", "vps_deployment.build_release"]\nassets = ["release.json"]',
      );
      env.set('GH_TOKEN', 'package-token');
      env.set('GITHUB_ACTOR', 'publisher');
      repo.setHeadSha('reviewed-sha');
      registries.setPublished({});
      const [batch] = await planReleases('ci-image-v3.4.5');
      ensure(batch !== undefined, 'container batch must be planned');
      await use({ batch, ...createContainerPublication(shell, registries) });
    },
    expectGithubRelease: makeFixture(expectGithubRelease),
    expectNpmPublish: makeFixture(expectNpmPublish),
    expectPypiPublish: makeFixture(expectPypiPublish),
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
    npmTarget: async ({ shell, tempDir }, use) => {
      await use(createNpmTarget(shell, tempDir));
    },
    planReleases: async ({ airlock, logs }, use) => {
      await use(async (tag?) => {
        await airlock.run('plan', ...(tag === undefined ? [] : ['--tag', tag]));
        return parseJson(logs.logLines.at(-1) ?? '', ReleasePlanSchema).include;
      });
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
      async ({ repo, shell, tempDir }, use) => {
        repo.setRoot(tempDir.path);
        const targets = await seedReleaseTargets(tempDir);
        shell.on('pnpm pack', '');
        shell.on('tar -xOf', () => {
          const archive = shell.calls.at(-1)?.argv[1];
          const packed = shell.calls.findLast(call => call.program === 'pnpm' && call.argv.includes(archive ?? ''));
          ensure(packed?.cwd !== undefined, 'packed package directory must be supplied');
          return readFileSync(path.join(packed.cwd, 'package.json'), 'utf8');
        });
        shell.on('pnpm list', () => {
          const manifest = readFileSync(path.join(targets.util.dir, 'package.json'), 'utf8');
          return JSON.stringify([
            {
              private: false,
              ...parseJson(manifest, VersionFileSchema),
              path: targets.util.dir,
            },
          ]);
        });
        await use(targets);
      },
      { auto: true },
    ],
  })
  .extend('bundledConsumer', async ({ loadArtifact, shell, targets, tempDir }) =>
    createBundledConsumer({ loadArtifact, shell, targets, tempDir }),
  );
export type ReleaseTest = typeof releaseTest;
export const test = extendSurfaceChecks(releaseTest);
export { describe, expect } from 'vitest';
