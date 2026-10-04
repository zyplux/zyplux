import { libraryTest } from '@zyplux/spectra/library-test-api';
import { PackageJsonSchema, PyProjectSchema } from '@zyplux/util/contracts';
import { parseJson } from '@zyplux/util/json';
import {
  findManifests,
  normalizePythonName,
  npmDependencyNames,
  pythonRequirementNames,
  repositoryUrl,
} from '@zyplux/util/manifest';
import { parseToml } from '@zyplux/util/toml';

import { createNestedGitRepos, workspaceRoot } from './nested-repositories.ts';

export const test = libraryTest
  .extend('findManifests', () => findManifests)
  .extend('normalizePythonName', () => normalizePythonName)
  .extend('npmDependencyNames', () => npmDependencyNames)
  .extend('parseJson', () => parseJson)
  .extend('parseToml', () => parseToml)
  .extend('pythonRequirementNames', () => pythonRequirementNames)
  .extend('repositoryUrl', () => repositoryUrl)
  .extend('createNestedGitRepos', () => createNestedGitRepos)
  .extend('packageJsonSchema', () => PackageJsonSchema)
  .extend('pyProjectSchema', () => PyProjectSchema)
  .extend('workspaceRoot', () => workspaceRoot);

export { describe, expect } from 'vitest';
