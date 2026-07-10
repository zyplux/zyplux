import { readdir } from 'node:fs/promises';
import path from 'node:path';

import type { PackageJson, PyProject } from './contracts';

import { attemptAsync } from './result';
import { $ } from './shell';

const LOCAL_NPM_PROTOCOL = /^(file|link|portal|workspace):/;
const PYTHON_REQUIREMENT_NAME = /^\s*([A-Za-z0-9][A-Za-z0-9._-]*)/;
const NPM_DEPENDENCY_FIELDS = ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const;
const MANIFEST_BASENAMES = new Set(['package.json', 'pyproject.toml']);

export const repositoryUrl = (repository: PackageJson['repository']) =>
  typeof repository === 'string' ? repository : repository?.url;

export const normalizePythonName = (requirement: string) => {
  const name = PYTHON_REQUIREMENT_NAME.exec(requirement)?.[1];
  if (name === undefined) return;
  return name.toLowerCase().replaceAll(/[-_.]+/g, '-');
};

const catalogNames = ({ catalog, catalogs, workspaces }: PackageJson): string[] => {
  const catalogMaps: Record<string, unknown>[] = [];
  if (catalog !== undefined) catalogMaps.push(catalog);
  if (catalogs !== undefined) catalogMaps.push(...Object.values(catalogs));
  const names = catalogMaps.flatMap(catalogMap => Object.keys(catalogMap));
  if (workspaces !== undefined && !Array.isArray(workspaces)) names.push(...catalogNames(workspaces));
  return names;
};

const declaredNpmNames = (manifest: PackageJson) => {
  const names: string[] = [];
  for (const field of NPM_DEPENDENCY_FIELDS) {
    const entries = Object.entries(manifest[field] ?? {});
    for (const [name, spec] of entries) {
      if (typeof spec === 'string' && !LOCAL_NPM_PROTOCOL.test(spec)) names.push(name);
    }
  }
  return names;
};

export const npmDependencyNames = (manifest: PackageJson) => [...catalogNames(manifest), ...declaredNpmNames(manifest)];

export const pythonRequirementNames = (manifest: PyProject) => {
  const requirements: string[] = [];
  const collectStrings = (items: readonly unknown[] | undefined) => {
    const list = items ?? [];
    for (const item of list) if (typeof item === 'string') requirements.push(item);
  };

  collectStrings(manifest.project?.dependencies);
  const optionalGroups = Object.values(manifest.project?.['optional-dependencies'] ?? {});
  for (const group of optionalGroups) collectStrings(group);
  const dependencyGroups = Object.values(manifest['dependency-groups'] ?? {});
  for (const group of dependencyGroups) collectStrings(group);
  collectStrings(manifest.tool?.uv?.['dev-dependencies']);

  const names: string[] = [];
  for (const requirement of requirements) {
    const name = normalizePythonName(requirement);
    if (name !== undefined && name !== 'python') names.push(name);
  }
  return names;
};

export const checkInsideWorkTree = async (dir: string) => {
  const probe = await $.git.isInsideWorkTree(dir);
  return probe.exitCode === 0 && probe.text().trim() === 'true';
};

const trackedManifests = async (dir: string) => {
  const result = await $.git.lsFiles(dir);
  const listing = result.text();
  const found: string[] = [];
  for (const relative of listing.split('\0')) {
    if (relative === '') continue;
    const basename = relative.slice(relative.lastIndexOf('/') + 1);
    if (MANIFEST_BASENAMES.has(basename)) found.push(path.join(dir, relative));
  }
  return found;
};

export const findGitRepos = async (dir: string) => {
  const repos: string[] = [];
  const visit = async (current: string) => {
    const listing = await attemptAsync(() => readdir(current, { withFileTypes: true }));
    if (!listing.ok) return;
    const entries = listing.data;
    if (entries.some(entry => entry.name === '.git')) {
      repos.push(current);
      return;
    }
    for (const entry of entries) {
      if (entry.isDirectory() && entry.name !== 'node_modules') {
        await visit(path.join(current, entry.name));
      }
    }
  };
  await visit(dir);
  return repos;
};

export const findManifests = async (dir: string) => {
  if (await checkInsideWorkTree(dir)) return trackedManifests(dir);
  const repos = await findGitRepos(dir);
  const listings = await Promise.all(repos.map(repo => trackedManifests(repo)));
  return listings.flat();
};
