import {
  findManifests,
  normalizePythonName,
  npmDependencyNames,
  PackageJsonSchema,
  PyProjectSchema,
  pythonRequirementNames,
  repositoryUrl,
} from '@zyplux/util/manifest';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));

describe('PackageJsonSchema', () => {
  it('reads a bun workspace catalog alongside dependency maps', () => {
    const manifest = PackageJsonSchema.parse({
      dependencies: { zod: 'catalog:' },
      name: '@scope/app',
      workspaces: { catalog: { react: '^19' } },
    });
    expect(manifest.name).toBe('@scope/app');
    expect(manifest.dependencies).toEqual({ zod: 'catalog:' });
    expect(manifest.workspaces).toEqual({ catalog: { react: '^19' } });
  });

  it('tolerates the array form of workspaces', () => {
    const manifest = PackageJsonSchema.parse({ workspaces: ['packages/*'] });
    expect(manifest.workspaces).toEqual(['packages/*']);
  });
});

describe('PyProjectSchema', () => {
  it('reads PEP 621 dependencies, optional groups, and PEP 735 dependency-groups', () => {
    const manifest = PyProjectSchema.parse({
      'dependency-groups': { dev: ['ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28'], name: 'app', 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });
    expect(manifest.project?.dependencies).toEqual(['httpx>=0.28']);
    expect(manifest.project?.['optional-dependencies']).toEqual({ http: ['urllib3'] });
    expect(manifest['dependency-groups']).toEqual({ dev: ['ruff>=0.1'] });
    expect(manifest.tool?.uv?.['dev-dependencies']).toEqual(['pytest>=8']);
  });
});

describe('npmDependencyNames', () => {
  it('collects catalog and dependency-field names, skipping workspace-local specs', () => {
    const manifest = PackageJsonSchema.parse({
      dependencies: { '@scope/local': 'workspace:*', react: '^19' },
      devDependencies: { vitest: 'catalog:' },
      workspaces: { catalog: { zod: 'catalog:' }, catalogs: { build: { esbuild: '^0.21' } } },
    });
    expect(npmDependencyNames(manifest)).toEqual(expect.arrayContaining(['esbuild', 'react', 'vitest', 'zod']));
    expect(npmDependencyNames(manifest)).not.toContain('@scope/local');
  });
});

describe('pythonRequirementNames', () => {
  it('normalizes requirements across every section and drops python itself', () => {
    const manifest = PyProjectSchema.parse({
      'dependency-groups': { dev: ['Ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28', 'python>=3.12'], 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });
    expect(pythonRequirementNames(manifest)).toEqual(expect.arrayContaining(['httpx', 'pytest', 'ruff', 'urllib3']));
    expect(pythonRequirementNames(manifest)).not.toContain('python');
  });
});

describe('repositoryUrl', () => {
  it('reads the url from string and object repository fields', () => {
    expect(repositoryUrl('https://github.com/owner/repo')).toBe('https://github.com/owner/repo');
    expect(repositoryUrl({ url: 'git+https://github.com/owner/repo.git' })).toBe(
      'git+https://github.com/owner/repo.git',
    );
    expect(repositoryUrl(undefined)).toBeUndefined();
  });
});

describe('normalizePythonName', () => {
  it('lowercases and collapses separators to the PEP 503 canonical form', () => {
    expect(normalizePythonName('Flask_SQLAlchemy')).toBe('flask-sqlalchemy');
    expect(normalizePythonName('ruamel.yaml >= 0.18')).toBe('ruamel-yaml');
    expect(normalizePythonName('\t \n')).toBeUndefined();
  });
});

describe('findManifests', () => {
  it('lists tracked manifests under the repo and excludes ignored paths', async () => {
    const manifests = await findManifests(workspaceRoot);
    expect(manifests.every(file => file.endsWith('package.json') || file.endsWith('pyproject.toml'))).toBe(true);
    expect(manifests.some(file => file.endsWith('/packages/util/package.json'))).toBe(true);
    expect(manifests.every(file => !file.includes('/node_modules/'))).toBe(true);
  });
});
