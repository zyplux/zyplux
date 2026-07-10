import {
  $,
  findManifests,
  mapWithConcurrency,
  normalizePythonName,
  normalizeRepoUrl,
  npmDependencyNames,
  parseJson,
  parseToml,
  poll,
  pythonRequirementNames,
  readTrimmed,
  repositoryUrl,
  tryParseToml,
} from '@zyplux/util';
import { PackageJsonSchema, PyProjectSchema } from '@zyplux/util/contracts';

export type Shell = typeof $;

export const subjects = {
  $,
  findManifests,
  mapWithConcurrency,
  normalizePythonName,
  normalizeRepoUrl,
  npmDependencyNames,
  packageJsonSchema: PackageJsonSchema,
  parseJson,
  parseToml,
  poll,
  pyProjectSchema: PyProjectSchema,
  pythonRequirementNames,
  readTrimmed,
  repositoryUrl,
  tryParseToml,
};

export type Subjects = typeof subjects;
