import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { describe, expect, test } from '#fixtures';

const byLocale = (left: string, right: string) => left.localeCompare(right);

const NESTED_REPO_MANIFESTS = { 'service-a': 'package.json', 'service-b': 'pyproject.toml' } as const;

const createNestedGitRepos = async (reposRoot: string) => {
  const manifestPaths: string[] = [];
  for (const [repoName, manifestName] of Object.entries(NESTED_REPO_MANIFESTS)) {
    const repoDir = path.join(reposRoot, repoName);
    await mkdir(repoDir, { recursive: true });
    execFileSync('git', ['init', '--quiet'], { cwd: repoDir, stdio: 'ignore' });
    await writeFile(path.join(repoDir, manifestName), '{}');
    execFileSync('git', ['add', manifestName], { cwd: repoDir, stdio: 'ignore' });
    manifestPaths.push(path.join(repoDir, manifestName));
  }
  return manifestPaths;
};

const packageJsonText = [
  '{',
  '  "name": "@scope/app",',
  '  "dependencies": { "zod": "catalog:" },',
  '  "workspaces": { "catalog": { "react": "^19" } },',
  '  "scripts": { "build": "bun build" }',
  '}',
].join('\n');

const pyprojectTomlText = [
  '[project]',
  'name = "app"',
  'dependencies = ["httpx>=0.28"]',
  '',
  '[project.optional-dependencies]',
  'http = ["urllib3"]',
  '',
  '[dependency-groups]',
  'dev = ["ruff>=0.1"]',
  '',
  '[tool.uv]',
  'dev-dependencies = ["pytest>=8"]',
  '',
  '[build-system]',
  'requires = ["hatchling"]',
].join('\n');

describe('1.1 parsing manifest text into typed shapes', () => {
  test('1.1.1 parses package json text into a typed manifest and strips unknown keys', ({ PackageJsonSchema, parseJson }) => {
    const manifest = parseJson(packageJsonText, PackageJsonSchema);

    expect(manifest).toEqual({
      dependencies: { zod: 'catalog:' },
      name: '@scope/app',
      workspaces: { catalog: { react: '^19' } },
    });
    expect(manifest).not.toHaveProperty('scripts');
  });

  test('1.1.2 tolerates the array form of workspaces', ({ PackageJsonSchema, parseJson }) => {
    const manifest = parseJson('{ "workspaces": ["packages/*"] }', PackageJsonSchema);

    expect(manifest).toEqual({ workspaces: ['packages/*'] });
  });

  test('1.1.3 parses pyproject toml text with pep 621 and pep 735 dependency sections and strips unknown keys', ({ parseToml, PyProjectSchema }) => {
    const manifest = parseToml(pyprojectTomlText, PyProjectSchema);

    expect(manifest).toEqual({
      'dependency-groups': { dev: ['ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28'], name: 'app', 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });
    expect(manifest).not.toHaveProperty('build-system');
  });
});

describe('1.2 collecting and normalizing dependency names from a manifest', () => {
  test('1.2.1 collects npm catalog and dependency field names while skipping workspace local specs', ({ npmDependencyNames, PackageJsonSchema }) => {
    const manifest = PackageJsonSchema.parse({
      dependencies: { '@scope/local': 'workspace:*', react: '^19' },
      devDependencies: { vitest: 'catalog:' },
      workspaces: { catalog: { zod: 'catalog:' }, catalogs: { build: { esbuild: '^0.21' } } },
    });

    expect(npmDependencyNames(manifest).toSorted(byLocale)).toEqual(['esbuild', 'react', 'vitest', 'zod']);
  });

  test('1.2.2 collects python requirement names across every section while dropping python itself', ({ PyProjectSchema, pythonRequirementNames }) => {
    const manifest = PyProjectSchema.parse({
      'dependency-groups': { dev: ['Ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28', 'python>=3.12'], 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });

    expect(pythonRequirementNames(manifest).toSorted(byLocale)).toEqual(['httpx', 'pytest', 'ruff', 'urllib3']);
  });

  test('1.2.3 normalizes a requirement name into its pep 503 canonical form', ({ normalizePythonName }) => {
    expect(normalizePythonName('Flask_SQLAlchemy')).toBe('flask-sqlalchemy');
    expect(normalizePythonName('ruamel.yaml >= 0.18')).toBe('ruamel-yaml');
  });

  test('1.2.4 returns undefined when no package name can be parsed from a requirement', ({ normalizePythonName }) => {
    expect(normalizePythonName('\t \n')).toBeUndefined();
  });
});

describe("1.3 resolving a manifest's repository url", () => {
  test('1.3.1 reads the url from a string repository field', ({ repositoryUrl }) => {
    expect(repositoryUrl('https://github.com/owner/repo')).toBe('https://github.com/owner/repo');
  });

  test('1.3.2 reads the url from an object repository field', ({ repositoryUrl }) => {
    expect(repositoryUrl({ url: 'git+https://github.com/owner/repo.git' })).toBe(
      'git+https://github.com/owner/repo.git',
    );
  });

  test('1.3.3 returns undefined when no repository is declared', ({ repositoryUrl }) => {
    expect(repositoryUrl(undefined)).toBeUndefined();
  });
});

describe('1.4 discovering manifests tracked by git', () => {
  test('1.4.1 lists tracked manifests under the repo and excludes ignored paths', async ({ findManifests, workspaceRoot }) => {
    const manifests = await findManifests(workspaceRoot);

    expect({
      allAreManifestFiles: manifests.every(file => file.endsWith('package.json') || file.endsWith('pyproject.toml')),
      excludesNodeModules: manifests.every(file => !file.includes('/node_modules/')),
      includesUtilPackageJson: manifests.some(file => file.endsWith('/packages/util-ts/package.json')),
    }).toEqual({ allAreManifestFiles: true, excludesNodeModules: true, includesUtilPackageJson: true });
  });

  test('1.4.2 discovers manifests across nested repositories when the directory itself is outside any repository', async ({
    findManifests,
    tempDir,
  }) => {
    const expectedManifests = await createNestedGitRepos(tempDir.path);

    const manifests = await findManifests(tempDir.path);

    expect(manifests.toSorted(byLocale)).toEqual(expectedManifests.toSorted(byLocale));
  });
});
