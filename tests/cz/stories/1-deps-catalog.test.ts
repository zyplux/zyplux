import type { PackageSystem } from '@zyplux/cz/deps-catalog';

import { collectDepRepos, collectDepsNames, resolveSourceRepo } from '@zyplux/cz/deps-catalog';
import { fakeShellOutput, fakeShellPromise, toArgv } from '@zyplux/tests-shell-fixtures';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, test as base, beforeEach, describe, expect, vi } from 'vitest';

type FetchRoute = (url: string) => Response;

const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));

const byLocale = (left: string, right: string) => left.localeCompare(right);

const notFound = () => Response.error();
const depsDevDefaultVersion = () =>
  Response.json({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });
const depsDevSourceRepo = (id: string) =>
  Response.json({ relatedProjects: [{ projectKey: { id }, relationType: 'SOURCE_REPO' }] });

const reactViaDepsDev: FetchRoute = url =>
  url.includes('/versions/') ? depsDevSourceRepo('github.com/facebook/react') : depsDevDefaultVersion();

const zodViaDepsDevLinks: FetchRoute = url =>
  url.includes('/versions/')
    ? Response.json({ links: [{ label: 'SOURCE_REPO', url: 'https://github.com/colinhacks/zod' }] })
    : depsDevDefaultVersion();

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

const sourceRepoById = new Map([
  ['npm:@optique/core', 'github.com/dahlia/optique'],
  ['npm:knip', 'github.com/zyplux/zyplux'],
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

const stubGitTree = (listing: string) => {
  const shellFn = vi.fn<typeof Bun.$>();
  shellFn.mockImplementation((strings, ...values) => {
    const argv = toArgv(values);
    if (argv[0] === 'rev-parse') return fakeShellPromise(fakeShellOutput('true\n'));
    if (argv[0] === 'ls-files') return fakeShellPromise(fakeShellOutput(listing));
    throw new Error(`unexpected Bun.$ call: ${strings[0]?.trim() ?? ''} ${argv.join(' ')}`);
  });
  Bun.$ = shellFn;
};

const test = base.extend<{
  depRepos: Awaited<ReturnType<typeof collectDepRepos>>;
  depsCatalog: Awaited<ReturnType<typeof collectDepsNames>>;
  resolveRepo: (route: FetchRoute, system: PackageSystem, name: string) => Promise<string | undefined>;
}>({
  depRepos: async ({}, use) => {
    vi.stubGlobal('fetch', (input: string | URL) => Promise.resolve(resolveFromCatalog(String(input))));
    try {
      await use(await collectDepRepos({ dir: workspaceRoot }));
    } finally {
      vi.unstubAllGlobals();
    }
  },

  depsCatalog: async ({}, use) => {
    await use(await collectDepsNames(workspaceRoot));
  },

  resolveRepo: async ({}, use) => {
    try {
      await use((route, system, name) => {
        vi.stubGlobal('fetch', (input: string | URL) => Promise.resolve(route(String(input))));
        return resolveSourceRepo(system, name);
      });
    } finally {
      vi.unstubAllGlobals();
    }
  },
});

describe('1.1 scanning workspace manifests for declared dependency names', () => {
  test('1.1.1 collects npm dependency names from bun catalogs', ({ depsCatalog }) => {
    expect(depsCatalog.npm).toEqual(
      expect.arrayContaining(['@optique/core', '@optique/run', 'eslint', 'typescript', 'vitest', 'zod']),
    );
  });

  test('1.1.2 collects python dependency names from project dependencies and dependency groups', ({ depsCatalog }) => {
    expect(depsCatalog.pypi).toEqual(
      expect.arrayContaining(['pyrefly', 'pytest', 'pyyaml', 'ruff', 'rumdl', 'typer', 'vulture']),
    );
  });

  test('1.1.3 excludes internal workspace packages from both ecosystems', ({ depsCatalog }) => {
    expect(depsCatalog.npm).toEqual(expect.not.arrayContaining(['@zyplux/util', '@zyplux/cz', '@zyplux/tsconfig']));
    expect(depsCatalog.pypi).toEqual(expect.not.arrayContaining(['zyplux', 'zyplux-cerberus']));
  });

  test('1.1.4 returns sorted deduplicated names for each ecosystem', ({ depsCatalog }) => {
    expect(depsCatalog.npm).toEqual([...new Set(depsCatalog.npm)].toSorted(byLocale));
    expect(depsCatalog.pypi).toEqual([...new Set(depsCatalog.pypi)].toSorted(byLocale));
  });
});

describe('1.2 resolving a dependency name to its source repository', () => {
  test('1.2.1 resolves a package to its source repo via deps dev', async ({ resolveRepo }) => {
    expect(await resolveRepo(reactViaDepsDev, 'npm', 'react')).toBe('https://github.com/facebook/react');
  });

  test('1.2.2 falls back to the npm registry when deps dev has no source repo', async ({ resolveRepo }) => {
    expect(await resolveRepo(reactViaNpmRegistry, 'npm', 'react')).toBe('https://github.com/facebook/react');
  });

  test('1.2.3 falls back to pypi project urls when deps dev has no source repo', async ({ resolveRepo }) => {
    expect(await resolveRepo(requestsViaPypi, 'pypi', 'requests')).toBe('https://github.com/psf/requests');
  });

  test('1.2.4 returns undefined when no source repo is found anywhere', async ({ resolveRepo }) => {
    expect(await resolveRepo(nothingAnywhere, 'npm', 'does-not-exist')).toBeUndefined();
  });

  test('1.2.5 falls back to a deps dev links entry when there is no related project', async ({ resolveRepo }) => {
    expect(await resolveRepo(zodViaDepsDevLinks, 'npm', 'zod')).toBe('https://github.com/colinhacks/zod');
  });
});

describe('1.3 collecting the external repos a workspace depends on', () => {
  test('1.3.1 collects deduplicated sorted source repos for resolved dependencies', ({ depRepos }) => {
    expect(depRepos.repos).toEqual(
      expect.arrayContaining([
        'https://github.com/astral-sh/ruff',
        'https://github.com/colinhacks/zod',
        'https://github.com/dahlia/optique',
      ]),
    );
    expect(depRepos.repos).toEqual([...new Set(depRepos.repos)].toSorted(byLocale));
  });

  test('1.3.2 excludes repos that belong to the scanned workspace itself', ({ depRepos }) => {
    expect(depRepos.repos).not.toContain('https://github.com/zyplux/zyplux');
  });

  test('1.3.3 reports dependencies it could not resolve to a repo', ({ depRepos }) => {
    expect(depRepos.unresolved).toEqual(
      expect.arrayContaining([
        { name: 'eslint', system: 'npm' },
        { name: 'pytest', system: 'pypi' },
      ]),
    );
  });

  test('1.3.4 defaults to the current working directory and no local repos when called without options', async () => {
    vi.stubGlobal('fetch', (input: string | URL) => Promise.resolve(resolveFromCatalog(String(input))));
    try {
      const withDefaults = await collectDepRepos();

      expect(withDefaults.repos).toEqual(
        expect.arrayContaining(['https://github.com/astral-sh/ruff', 'https://github.com/dahlia/optique']),
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  test('1.3.5 excludes extra local repos passed via options, ignoring ones that fail to normalize', async () => {
    vi.stubGlobal('fetch', (input: string | URL) => Promise.resolve(resolveFromCatalog(String(input))));
    try {
      const withExtraRepo = await collectDepRepos({
        dir: workspaceRoot,
        localRepos: ['https://github.com/colinhacks/zod.git', ''],
      });

      expect(withExtraRepo.repos).not.toContain('https://github.com/colinhacks/zod');
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('1.4 skipping manifest files that fail to parse', () => {
  let dir: string;
  const originalBunDollar = Bun.$;

  beforeEach(async () => {
    dir = await mkdtemp(path.join(tmpdir(), 'cz-deps-catalog-broken-'));
    await writeFile(path.join(dir, 'package.json'), '{ "name": "should-not-parse", ', 'utf8');
    await mkdir(path.join(dir, 'bad-toml'));
    await writeFile(path.join(dir, 'bad-toml/pyproject.toml'), '[project\nname = "should-not-parse"\n', 'utf8');
    await mkdir(path.join(dir, 'no-name'));
    await writeFile(
      path.join(dir, 'no-name/pyproject.toml'),
      '[project.urls]\nSource = "https://github.com/noname/repo"\n',
      'utf8',
    );
    await mkdir(path.join(dir, 'empty-name'));
    await writeFile(
      path.join(dir, 'empty-name/pyproject.toml'),
      '[project]\nname = ""\n\n[project.urls]\nSource = "https://github.com/emptyname/repo"\n',
      'utf8',
    );
    stubGitTree(
      ['package.json', 'bad-toml/pyproject.toml', 'no-name/pyproject.toml', 'empty-name/pyproject.toml']
        .map(relative => `${relative}\0`)
        .join(''),
    );
  });

  afterEach(async () => {
    Bun.$ = originalBunDollar;
    await rm(dir, { force: true, recursive: true });
  });

  test('1.4.1 skips package.json and pyproject.toml files that fail to parse, keeping the rest', async () => {
    const survivingRepos = ['https://github.com/noname/repo', 'https://github.com/emptyname/repo'];
    const scan = await collectDepsNames(dir);

    expect([...scan.localRepos]).toEqual(expect.arrayContaining(survivingRepos));
    expect(scan.localRepos.size).toBe(survivingRepos.length);
  });
});
