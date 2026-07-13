import { tryParseJson } from '@zyplux/util';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import type { WorkspaceManifest } from '#contracts';

import { WorkspaceManifestSchema } from '#contracts';
import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types';

const WILDCARD_SUFFIX = '/*';
const TESTS_DIR_PREFIX = 'tests/';

const readManifest = (packageJsonPath: string) => {
  try {
    return tryParseJson(readFileSync(packageJsonPath, 'utf8'), WorkspaceManifestSchema);
  } catch {
    return;
  }
};

const workspaceGlobs = (manifest: undefined | WorkspaceManifest) => {
  const { workspaces } = manifest ?? {};
  if (workspaces === undefined) return [];
  return Array.isArray(workspaces) ? workspaces : (workspaces.packages ?? []);
};

const globMemberDirs = (root: string, glob: string) => {
  if (!glob.endsWith(WILDCARD_SUFFIX)) return [];
  const parentDir = glob.slice(0, -WILDCARD_SUFFIX.length);
  try {
    return readdirSync(path.join(root, parentDir), { withFileTypes: true })
      .filter(entry => entry.isDirectory())
      .map(entry => `${parentDir}/${entry.name}`);
  } catch {
    return [];
  }
};

const subjectEntries = (root: string, glob: string) =>
  globMemberDirs(root, glob)
    .filter(member => !member.startsWith(TESTS_DIR_PREFIX))
    .flatMap(member => {
      const name = readManifest(path.join(root, member, 'package.json'))?.name;
      return name === undefined ? [] : [{ basename: member.slice(member.lastIndexOf('/') + 1), name }];
    });

const subjectNamesByBasename = (root: string) => {
  const rootManifest = readManifest(path.join(root, 'package.json'));
  const entries = workspaceGlobs(rootManifest).flatMap(glob => subjectEntries(root, glob));
  return new Map(entries.map(({ basename, name }) => [basename, name] as const));
};

const suiteBasenames = (testsRoot: string) => {
  try {
    return readdirSync(testsRoot, { withFileTypes: true })
      .filter(entry => entry.isDirectory())
      .map(entry => entry.name);
  } catch {
    return [];
  }
};

export const fixtureRoleConfigs = (root: string): ConfigWithExtends[] => {
  const subjects = subjectNamesByBasename(root);
  const testsRoot = path.join(root, 'tests');
  return suiteBasenames(testsRoot).flatMap(basename => {
    const subject = subjects.get(basename);
    if (subject === undefined) return [];
    return [
      {
        files: [`tests/${basename}/fixtures/*.{ts,tsx}`],
        ignores: [`tests/${basename}/fixtures/{arrange,act}.{ts,tsx}`],
        plugins: { '@zyplux': plugin },
        rules: { '@zyplux/fixture-role-imports': ['error', { subject }] },
      },
    ];
  });
};
