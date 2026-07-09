import {
  $,
  findManifests,
  mapWithConcurrency,
  normalizePythonName,
  normalizeRepoUrl,
  npmDependencyNames,
  PackageJsonSchema,
  parseJson,
  parseToml,
  poll,
  PyProjectSchema,
  pythonRequirementNames,
  readTrimmed,
  repositoryUrl,
  tryParseToml,
} from '@zyplux/util';

export type Shell = typeof $;

export const subjects = {
  $,
  findManifests,
  mapWithConcurrency,
  normalizePythonName,
  normalizeRepoUrl,
  npmDependencyNames,
  PackageJsonSchema,
  parseJson,
  parseToml,
  poll,
  PyProjectSchema,
  pythonRequirementNames,
  readTrimmed,
  repositoryUrl,
  tryParseToml,
};

export type Subjects = typeof subjects;
