import {
  findManifests,
  normalizePythonName,
  npmDependencyNames,
  PackageJsonSchema,
  PyProjectSchema,
  pythonRequirementNames,
  repositoryUrl,
} from '@zyplux/util/manifest';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));

const byLocale = (left: string, right: string) => left.localeCompare(right);

const NESTED_REPO_MANIFESTS = { 'service-a': 'package.json', 'service-b': 'pyproject.toml' } as const;

const createNestedGitRepos = async () => {
  const reposRoot = await mkdtemp(path.join(tmpdir(), 'zyplux-manifest-'));
  for (const [repoName, manifestName] of Object.entries(NESTED_REPO_MANIFESTS)) {
    const repoDir = path.join(reposRoot, repoName);
    await mkdir(repoDir, { recursive: true });
    execFileSync('git', ['init', '--quiet'], { cwd: repoDir, stdio: 'ignore' });
    await writeFile(path.join(repoDir, manifestName), '{}');
    execFileSync('git', ['add', manifestName], { cwd: repoDir, stdio: 'ignore' });
  }
  return reposRoot;
};

describe('1.1 parsing package manifests into typed shapes', () => {
  it('1.1.1 reads a bun workspace catalog alongside dependency maps', () => {
    const manifest = PackageJsonSchema.parse({
      dependencies: { zod: 'catalog:' },
      name: '@scope/app',
      workspaces: { catalog: { react: '^19' } },
    });

    expect(manifest).toEqual({
      dependencies: { zod: 'catalog:' },
      name: '@scope/app',
      workspaces: { catalog: { react: '^19' } },
    });
  });

  it('1.1.2 tolerates the array form of workspaces', () => {
    const manifest = PackageJsonSchema.parse({ workspaces: ['packages/*'] });

    expect(manifest).toEqual({ workspaces: ['packages/*'] });
  });

  it('1.1.3 reads pep 621 dependencies optional dependency groups and pep 735 dependency groups', () => {
    const manifest = PyProjectSchema.parse({
      'dependency-groups': { dev: ['ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28'], name: 'app', 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });

    expect(manifest).toEqual({
      'dependency-groups': { dev: ['ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28'], name: 'app', 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });
  });
});

describe('1.2 collecting and normalizing dependency names from a manifest', () => {
  it('1.2.1 collects npm catalog and dependency field names while skipping workspace local specs', () => {
    const manifest = PackageJsonSchema.parse({
      dependencies: { '@scope/local': 'workspace:*', react: '^19' },
      devDependencies: { vitest: 'catalog:' },
      workspaces: { catalog: { zod: 'catalog:' }, catalogs: { build: { esbuild: '^0.21' } } },
    });

    expect(npmDependencyNames(manifest).toSorted(byLocale)).toEqual(['esbuild', 'react', 'vitest', 'zod']);
  });

  it('1.2.2 collects python requirement names across every section while dropping python itself', () => {
    const manifest = PyProjectSchema.parse({
      'dependency-groups': { dev: ['Ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28', 'python>=3.12'], 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });

    expect(pythonRequirementNames(manifest).toSorted(byLocale)).toEqual(['httpx', 'pytest', 'ruff', 'urllib3']);
  });

  it('1.2.3 normalizes a requirement name into its pep 503 canonical form', () => {
    expect(normalizePythonName('Flask_SQLAlchemy')).toBe('flask-sqlalchemy');
    expect(normalizePythonName('ruamel.yaml >= 0.18')).toBe('ruamel-yaml');
  });

  it('1.2.4 returns undefined when no package name can be parsed from a requirement', () => {
    expect(normalizePythonName('\t \n')).toBeUndefined();
  });
});

describe("1.3 resolving a manifest's repository url", () => {
  it('1.3.1 reads the url from a string repository field', () => {
    expect(repositoryUrl('https://github.com/owner/repo')).toBe('https://github.com/owner/repo');
  });

  it('1.3.2 reads the url from an object repository field', () => {
    expect(repositoryUrl({ url: 'git+https://github.com/owner/repo.git' })).toBe(
      'git+https://github.com/owner/repo.git',
    );
  });

  it('1.3.3 returns undefined when no repository is declared', () => {
    expect(repositoryUrl(undefined)).toBeUndefined();
  });
});

describe('1.4 discovering manifests tracked by git', () => {
  it('1.4.1 lists tracked manifests under the repo and excludes ignored paths', async () => {
    const manifests = await findManifests(workspaceRoot);

    expect({
      allAreManifestFiles: manifests.every(file => file.endsWith('package.json') || file.endsWith('pyproject.toml')),
      excludesNodeModules: manifests.every(file => !file.includes('/node_modules/')),
      includesUtilPackageJson: manifests.some(file => file.endsWith('/packages/util/package.json')),
    }).toEqual({ allAreManifestFiles: true, excludesNodeModules: true, includesUtilPackageJson: true });
  });

  it('1.4.2 discovers manifests across nested repositories when the directory itself is outside any repository', async () => {
    const root = await createNestedGitRepos();

    try {
      const manifests = await findManifests(root);

      expect(manifests.toSorted(byLocale)).toEqual(
        Object.entries(NESTED_REPO_MANIFESTS)
          .map(([repoName, manifestName]) => path.join(root, repoName, manifestName))
          .toSorted(byLocale),
      );
    } finally {
      await rm(root, { force: true, recursive: true });
    }
  });
});
