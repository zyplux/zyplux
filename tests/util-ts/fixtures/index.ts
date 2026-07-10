import { libraryTest, makeFixture } from '@zyplux/tests-fixtures';
import { ZodError } from 'zod';

import type { Subjects } from './act';

import { subjects } from './act';
import { createNestedGitRepos, workspaceRoot } from './arrange';

type ArrangeFixtures = {
  createNestedGitRepos: typeof createNestedGitRepos;
  workspaceRoot: string;
  zodError: typeof ZodError;
};

export const test = libraryTest.extend<ArrangeFixtures & Subjects>({
  $: makeFixture(subjects.$),
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
  tryParseToml: makeFixture(subjects.tryParseToml),
  workspaceRoot,
  zodError: makeFixture(ZodError),
});

export type { Shell } from './act';
export type { ShellFake } from '@zyplux/tests-fixtures';
export { describe, expect } from 'vitest';
