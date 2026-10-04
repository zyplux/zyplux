import { libraryTest, makeFixture } from '@zyplux/spectra/library-test-api';
import { setTimeout as sleep } from 'node:timers/promises';
import { vi } from 'vitest';

import type { Subjects } from './act.ts';

import { subjects } from './act.ts';
import { createNestedGitRepos, workspaceRoot } from './arrange.ts';
import { assertGhTypes } from './gh-types.ts';
import './matchers.ts';

type ArrangeFixtures = {
  assertGhTypes: typeof assertGhTypes;
  createNestedGitRepos: typeof createNestedGitRepos;
  sleep: typeof sleep;
  workspaceRoot: string;
};

export const test = libraryTest.extend<ArrangeFixtures & Subjects>({
  $: makeFixture(subjects.$),
  assertGhTypes: makeFixture(assertGhTypes),
  createNestedGitRepos: makeFixture(createNestedGitRepos),
  findManifests: makeFixture(subjects.findManifests),
  mapWithConcurrency: makeFixture(subjects.mapWithConcurrency),
  normalizePythonName: makeFixture(subjects.normalizePythonName),
  normalizeRepoUrl: makeFixture(subjects.normalizeRepoUrl),
  npmDependencyNames: makeFixture(subjects.npmDependencyNames),
  packageJsonSchema: makeFixture(subjects.packageJsonSchema),
  parseJson: makeFixture(subjects.parseJson),
  parseToml: makeFixture(subjects.parseToml),
  poll: makeFixture(subjects.poll),
  pyProjectSchema: makeFixture(subjects.pyProjectSchema),
  pythonRequirementNames: makeFixture(subjects.pythonRequirementNames),
  readTrimmed: makeFixture(subjects.readTrimmed),
  repositoryUrl: makeFixture(subjects.repositoryUrl),
  run: makeFixture(subjects.run),
  sleep: async ({}, use) => {
    vi.mocked(sleep).mockResolvedValue(undefined);
    try {
      await use(sleep);
    } finally {
      vi.mocked(sleep).mockReset();
    }
  },
  tryParseToml: makeFixture(subjects.tryParseToml),
  workspaceRoot,
});

export type { Shell } from './act.ts';
export type { TomlOutcome } from './matchers.ts';
export type { ShellFake } from '@zyplux/spectra/fakes/shell-fake';
export { describe, expect } from 'vitest';
