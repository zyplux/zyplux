import { libraryTest, makeFixture } from '@zyplux/tests-fixtures';

import type { Subjects } from './act';

import { subjects } from './act';
import { workspaceRoot } from './arrange';

type ArrangeFixtures = { workspaceRoot: string };

export const test = libraryTest.extend<ArrangeFixtures & Subjects>({
  $: makeFixture(subjects.$),
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
});

export type { Shell } from './act';
export type { ShellFake } from '@zyplux/tests-fixtures';
export { describe, expect } from 'vitest';
