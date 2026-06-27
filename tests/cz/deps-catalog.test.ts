import { collectDepRepos, collectDepsNames, resolveSourceRepo } from '@zyplux/cz/deps-catalog';
import { fileURLToPath } from 'node:url';
import { test as base, describe, expect, vi } from 'vitest';

type FetchRoute = (url: string) => Response;

const test = base.extend<{ routeFetch: (route: FetchRoute) => void }>({
  routeFetch: async ({}, use) => {
    try {
      await use(route => {
        vi.stubGlobal('fetch', (input: string | URL) => Promise.resolve(route(String(input))));
      });
    } finally {
      vi.unstubAllGlobals();
    }
  },
});

const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));

const byLocale = (left: string, right: string) => left.localeCompare(right);

const notFound = () => Response.error();
const depsDevDefaultVersion = () =>
  Response.json({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });
const depsDevSourceRepo = (id: string) =>
  Response.json({ relatedProjects: [{ projectKey: { id }, relationType: 'SOURCE_REPO' }] });

const reactViaDepsDev: FetchRoute = url =>
  url.includes('/versions/') ? depsDevSourceRepo('github.com/facebook/react') : depsDevDefaultVersion();

const reactViaNpmRegistry: FetchRoute = url => {
  if (url.startsWith('https://api.deps.dev/')) {
    return url.includes('/versions/') ? Response.json({ relatedProjects: [] }) : depsDevDefaultVersion();
  }
  if (url.startsWith('https://registry.npmjs.org/')) {
    return Response.json({ repository: { url: 'git+https://github.com/facebook/react.git' } });
  }
  return notFound();
};

const requestsViaPypi: FetchRoute = url => {
  if (url.startsWith('https://api.deps.dev/')) {
    return url.includes('/versions/') ? Response.json({}) : depsDevDefaultVersion();
  }
  if (url.startsWith('https://pypi.org/')) {
    return Response.json({ info: { project_urls: { Source: 'https://github.com/psf/requests' } } });
  }
  return notFound();
};

const nothingAnywhere: FetchRoute = () => notFound();

describe('collectDepsNames', () => {
  test('collects npm dependency names from bun catalogs', async () => {
    const { npm } = await collectDepsNames(workspaceRoot);

    expect(npm).toEqual(
      expect.arrayContaining(['@optique/core', '@optique/run', 'eslint', 'typescript', 'vitest', 'zod']),
    );
  });

  test('collects python dependency names from project dependencies and dependency groups', async () => {
    const { pypi } = await collectDepsNames(workspaceRoot);

    expect(pypi).toEqual(expect.arrayContaining(['pyrefly', 'pytest', 'pyyaml', 'ruff', 'rumdl', 'typer', 'vulture']));
  });

  test('excludes internal workspace packages from both ecosystems', async () => {
    const { npm, pypi } = await collectDepsNames(workspaceRoot);

    expect(npm).not.toContain('@zyplux/util');
    expect(npm).not.toContain('@zyplux/cz');
    expect(npm).not.toContain('@zyplux/tsconfig');
    expect(pypi).not.toContain('zyp-cerberus');
    expect(pypi).not.toContain('zyplux-cerberus');
  });

  test('returns sorted, de-duplicated names', async () => {
    const { npm, pypi } = await collectDepsNames(workspaceRoot);

    expect(npm).toEqual([...new Set(npm)].toSorted(byLocale));
    expect(pypi).toEqual([...new Set(pypi)].toSorted(byLocale));
  });
});

describe('resolveSourceRepo', () => {
  test('resolves an npm package to its source repo via deps.dev', async ({ routeFetch }) => {
    routeFetch(reactViaDepsDev);

    const repo = await resolveSourceRepo('npm', 'react');

    expect(repo).toBe('https://github.com/facebook/react');
  });

  test('falls back to the npm registry when deps.dev has no source repo', async ({ routeFetch }) => {
    routeFetch(reactViaNpmRegistry);

    const repo = await resolveSourceRepo('npm', 'react');

    expect(repo).toBe('https://github.com/facebook/react');
  });

  test('falls back to PyPI project_urls when deps.dev has no source repo', async ({ routeFetch }) => {
    routeFetch(requestsViaPypi);

    const repo = await resolveSourceRepo('pypi', 'requests');

    expect(repo).toBe('https://github.com/psf/requests');
  });

  test('returns undefined when no source repo is found anywhere', async ({ routeFetch }) => {
    routeFetch(nothingAnywhere);

    const repo = await resolveSourceRepo('npm', 'does-not-exist');

    expect(repo).toBeUndefined();
  });
});

describe('collectDepRepos', () => {
  const sourceRepoById = new Map([
    ['npm:@optique/core', 'github.com/dahlia/optique'],
    ['npm:knip', 'github.com/zyplux/zyp-cerberus'],
    ['npm:zod', 'github.com/colinhacks/zod'],
    ['pypi:ruff', 'github.com/astral-sh/ruff'],
  ]);

  const resolveFromCatalog: FetchRoute = url => {
    const match = /api\.deps\.dev\/v3\/systems\/([^/]+)\/packages\/([^/]+)(\/versions\/.+)?$/.exec(url);
    if (match === null) return notFound();
    const [, system, encodedName, versionPath] = match;
    if (system === undefined || encodedName === undefined) return notFound();
    const repo = sourceRepoById.get(`${system}:${decodeURIComponent(encodedName)}`);
    if (repo === undefined) return notFound();
    return versionPath === undefined ? depsDevDefaultVersion() : depsDevSourceRepo(repo);
  };

  test('collects deduped, sorted source repos for resolved dependencies', async ({ routeFetch }) => {
    routeFetch(resolveFromCatalog);

    const { repos } = await collectDepRepos({ dir: workspaceRoot });

    expect(repos).toEqual(
      expect.arrayContaining([
        'https://github.com/astral-sh/ruff',
        'https://github.com/colinhacks/zod',
        'https://github.com/dahlia/optique',
      ]),
    );
    expect(repos).toEqual([...new Set(repos)].toSorted(byLocale));
  });

  test('excludes repos that belong to the scanned workspace itself', async ({ routeFetch }) => {
    routeFetch(resolveFromCatalog);

    const { repos } = await collectDepRepos({ dir: workspaceRoot });

    expect(repos).not.toContain('https://github.com/zyplux/zyp-cerberus');
  });

  test('reports dependencies it could not resolve to a repo', async ({ routeFetch }) => {
    routeFetch(resolveFromCatalog);

    const { unresolved } = await collectDepRepos({ dir: workspaceRoot });

    expect(unresolved).toEqual(
      expect.arrayContaining([
        { name: 'eslint', system: 'npm' },
        { name: 'pytest', system: 'pypi' },
      ]),
    );
  });
});
