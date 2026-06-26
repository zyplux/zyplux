import { collectDependencyNames, collectDepRepos, resolveSourceRepo } from '@zyplux/cz/deps-catalog';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));

const byLocale = (left: string, right: string) => left.localeCompare(right);
const jsonResponse = (body: unknown) => Response.json(body);
const notFound = () => Response.error();

const depsDevDefaultVersion = () => jsonResponse({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });
const depsDevSourceRepo = (id: string) =>
  jsonResponse({ relatedProjects: [{ projectKey: { id }, relationType: 'SOURCE_REPO' }] });

const reactViaDepsDev = (input: string | URL) =>
  Promise.resolve(
    String(input).includes('/versions/') ? depsDevSourceRepo('github.com/facebook/react') : depsDevDefaultVersion(),
  );

const reactViaNpmRegistry = (input: string | URL) => {
  const url = String(input);
  if (url.startsWith('https://api.deps.dev/')) {
    return Promise.resolve(
      url.includes('/versions/') ? jsonResponse({ relatedProjects: [] }) : depsDevDefaultVersion(),
    );
  }
  if (url.startsWith('https://registry.npmjs.org/')) {
    return Promise.resolve(jsonResponse({ repository: { url: 'git+https://github.com/facebook/react.git' } }));
  }
  return Promise.resolve(notFound());
};

const requestsViaPypi = (input: string | URL) => {
  const url = String(input);
  if (url.startsWith('https://api.deps.dev/')) {
    return Promise.resolve(url.includes('/versions/') ? jsonResponse({}) : depsDevDefaultVersion());
  }
  if (url.startsWith('https://pypi.org/')) {
    return Promise.resolve(jsonResponse({ info: { project_urls: { Source: 'https://github.com/psf/requests' } } }));
  }
  return Promise.resolve(notFound());
};

const alwaysMissing = () => Promise.resolve(notFound());

describe('collectDependencyNames', () => {
  it('collects npm dependency names from bun catalogs', async () => {
    const { npm } = await collectDependencyNames(workspaceRoot);
    expect(npm).toEqual(
      expect.arrayContaining(['@optique/core', '@optique/run', 'eslint', 'typescript', 'vitest', 'zod']),
    );
  });

  it('collects python dependency names from project dependencies and dependency groups', async () => {
    const { pypi } = await collectDependencyNames(workspaceRoot);
    expect(pypi).toEqual(expect.arrayContaining(['pyrefly', 'pytest', 'pyyaml', 'ruff', 'rumdl', 'typer', 'vulture']));
  });

  it('excludes internal workspace packages from both ecosystems', async () => {
    const { npm, pypi } = await collectDependencyNames(workspaceRoot);
    expect(npm).not.toContain('@zyplux/util');
    expect(npm).not.toContain('@zyplux/cz');
    expect(npm).not.toContain('@zyplux/tsconfig');
    expect(pypi).not.toContain('zyp-cerberus');
    expect(pypi).not.toContain('zyplux-cerberus');
  });

  it('returns sorted, de-duplicated names', async () => {
    const { npm, pypi } = await collectDependencyNames(workspaceRoot);
    expect(npm).toEqual([...new Set(npm)].toSorted(byLocale));
    expect(pypi).toEqual([...new Set(pypi)].toSorted(byLocale));
  });
});

describe('resolveSourceRepo', () => {
  it('resolves an npm package to its source repo via deps.dev', async () => {
    expect(await resolveSourceRepo('npm', 'react', reactViaDepsDev)).toBe('https://github.com/facebook/react');
  });

  it('falls back to the npm registry when deps.dev has no source repo', async () => {
    expect(await resolveSourceRepo('npm', 'react', reactViaNpmRegistry)).toBe('https://github.com/facebook/react');
  });

  it('falls back to PyPI project_urls when deps.dev has no source repo', async () => {
    expect(await resolveSourceRepo('pypi', 'requests', requestsViaPypi)).toBe('https://github.com/psf/requests');
  });

  it('returns undefined when no source repo is found anywhere', async () => {
    expect(await resolveSourceRepo('npm', 'does-not-exist', alwaysMissing)).toBeUndefined();
  });
});

describe('collectDepRepos', () => {
  const sourceRepoById = new Map([
    ['npm:@optique/core', 'github.com/dahlia/optique'],
    ['npm:knip', 'github.com/zyplux/zyp-cerberus'],
    ['npm:zod', 'github.com/colinhacks/zod'],
    ['pypi:ruff', 'github.com/astral-sh/ruff'],
  ]);

  const fakeResolve = (input: string | URL) => {
    const url = String(input);
    const match = /api\.deps\.dev\/v3\/systems\/([^/]+)\/packages\/([^/]+)(\/versions\/.+)?$/.exec(url);
    if (match === null) return Promise.resolve(notFound());
    const [, system, encodedName, versionPath] = match;
    if (system === undefined || encodedName === undefined) return Promise.resolve(notFound());
    const repo = sourceRepoById.get(`${system}:${decodeURIComponent(encodedName)}`);
    if (repo === undefined) return Promise.resolve(notFound());
    return Promise.resolve(versionPath === undefined ? depsDevDefaultVersion() : depsDevSourceRepo(repo));
  };

  it('collects deduped, sorted source repos for resolved dependencies', async () => {
    const { repos } = await collectDepRepos({ dir: workspaceRoot, fetch: fakeResolve });
    expect(repos).toEqual(
      expect.arrayContaining([
        'https://github.com/astral-sh/ruff',
        'https://github.com/colinhacks/zod',
        'https://github.com/dahlia/optique',
      ]),
    );
    expect(repos).toEqual([...new Set(repos)].toSorted(byLocale));
  });

  it('excludes repos that belong to the scanned workspace itself', async () => {
    const { repos } = await collectDepRepos({ dir: workspaceRoot, fetch: fakeResolve });
    expect(repos).not.toContain('https://github.com/zyplux/zyp-cerberus');
  });

  it('reports dependencies it could not resolve to a repo', async () => {
    const { unresolved } = await collectDepRepos({ dir: workspaceRoot, fetch: fakeResolve });
    expect(unresolved).toEqual(
      expect.arrayContaining([
        { name: 'eslint', system: 'npm' },
        { name: 'pytest', system: 'pypi' },
      ]),
    );
  });
});
