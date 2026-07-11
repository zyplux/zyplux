import { describe, expect, test } from '#fixtures';

type FetchRoute = (url: string) => Response;

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

const depsDevRouteFor = (sourceRepoById: ReadonlyMap<string, string>) => (url: string) => {
  const match = /api\.deps\.dev\/v3\/systems\/([^/]+)\/packages\/([^/]+)(\/versions\/.+)?$/.exec(url);
  if (match === null) return notFound();
  const [, system, encodedName, versionPath] = match;
  if (system === undefined || encodedName === undefined) return notFound();
  const repo = sourceRepoById.get(`${system}:${decodeURIComponent(encodedName)}`);
  if (repo === undefined) return notFound();
  return versionPath === undefined ? depsDevDefaultVersion() : depsDevSourceRepo(repo);
};

const resolveFromWorkspaceCatalog = depsDevRouteFor(
  new Map([
    ['npm:@optique/core', 'github.com/dahlia/optique'],
    ['npm:knip', 'github.com/zyplux/zyplux'],
    ['npm:zod', 'github.com/colinhacks/zod'],
    ['pypi:ruff', 'github.com/astral-sh/ruff'],
  ]),
);

const npmManifest = (...dependencyNames: string[]) =>
  JSON.stringify({ dependencies: Object.fromEntries(dependencyNames.map(name => [name, '*'])), name: 'scratch-app' });

describe('1.1 scanning workspace manifests for declared dependency names', () => {
  test('1.1.1 collects npm dependency names from bun catalogs', async ({ catalog, network }) => {
    network.otherwise(nothingAnywhere);

    await catalog.runOverWorkspace();

    expect(catalog.unresolvedNames('npm')).toEqual(
      expect.arrayContaining(['@optique/core', '@optique/run', 'eslint', 'typescript', 'vitest', 'zod']),
    );
  });

  test('1.1.2 collects python dependency names from project dependencies and dependency groups', async ({
    catalog,
    network,
  }) => {
    network.otherwise(nothingAnywhere);

    await catalog.runOverWorkspace();

    expect(catalog.unresolvedNames('pypi')).toEqual(
      expect.arrayContaining(['pyrefly', 'pytest', 'pyyaml', 'ruff', 'rumdl', 'typer', 'vulture']),
    );
  });

  test('1.1.3 excludes internal workspace packages from both ecosystems', async ({ catalog, network }) => {
    network.otherwise(nothingAnywhere);

    await catalog.runOverWorkspace();

    expect(catalog.unresolvedNames('npm')).toEqual(
      expect.not.arrayContaining(['@zyplux/util', '@zyplux/cz', '@zyplux/tsconfig']),
    );
    expect(catalog.unresolvedNames('pypi')).toEqual(expect.not.arrayContaining(['zyplux', 'zyplux-cerberus']));
  });

  test('1.1.4 reports sorted deduplicated names for each ecosystem', async ({ catalog, network }) => {
    network.otherwise(nothingAnywhere);

    await catalog.runOverWorkspace();

    const npmNames = catalog.unresolvedNames('npm');
    const pypiNames = catalog.unresolvedNames('pypi');
    expect(npmNames).toEqual([...new Set(npmNames)].toSorted(byLocale));
    expect(pypiNames).toEqual([...new Set(pypiNames)].toSorted(byLocale));
  });
});

type ResolveCase = [
  shape: string,
  manifestPath: string,
  manifestText: string,
  route: FetchRoute,
  expectedRepos: string[],
  expectedUnresolvedNpm?: string[],
];

const resolveCases: ResolveCase[] = [
  [
    '1.2.1 resolves a package to its source repo via deps dev',
    'package.json',
    npmManifest('react'),
    reactViaDepsDev,
    ['https://github.com/facebook/react'],
  ],
  [
    '1.2.2 falls back to the npm registry when deps dev has no source repo',
    'package.json',
    npmManifest('react'),
    reactViaNpmRegistry,
    ['https://github.com/facebook/react'],
  ],
  [
    '1.2.3 falls back to pypi project urls when deps dev has no source repo',
    'pyproject.toml',
    '[project]\nname = "scratch-app"\ndependencies = ["requests"]\n',
    requestsViaPypi,
    ['https://github.com/psf/requests'],
  ],
  [
    '1.2.4 reports the dependency as unresolved when no source repo is found anywhere',
    'package.json',
    npmManifest('does-not-exist'),
    nothingAnywhere,
    [],
    ['does-not-exist'],
  ],
  [
    '1.2.5 falls back to a deps dev links entry when there is no related project',
    'package.json',
    npmManifest('zod'),
    zodViaDepsDevLinks,
    ['https://github.com/colinhacks/zod'],
  ],
];

describe('1.2 resolving a dependency name to its source repository', () => {
  test.for(resolveCases)(
    '%s',
    async ([, manifestPath, manifestText, route, expectedRepos, expectedUnresolvedNpm], { catalog, network }) => {
      await catalog.writeManifest(manifestPath, manifestText);
      network.otherwise(route);

      await catalog.run();

      if (expectedUnresolvedNpm !== undefined) {
        expect(catalog.unresolvedNames('npm')).toEqual(expectedUnresolvedNpm);
      }
      await expect(catalog.loadRepos()).resolves.toEqual(expectedRepos);
    },
  );
});

describe('1.3 collecting the external repos a workspace depends on', () => {
  test('1.3.1 collects deduplicated sorted source repos for resolved dependencies', async ({ catalog, network }) => {
    network.otherwise(resolveFromWorkspaceCatalog);

    await catalog.runOverWorkspace();

    const repos = await catalog.loadRepos();
    expect(repos).toEqual(
      expect.arrayContaining([
        'https://github.com/astral-sh/ruff',
        'https://github.com/colinhacks/zod',
        'https://github.com/dahlia/optique',
      ]),
    );
    expect(repos).toEqual([...new Set(repos)].toSorted(byLocale));
  });

  test('1.3.2 excludes repos that belong to the scanned workspace itself', async ({ catalog, network }) => {
    network.otherwise(resolveFromWorkspaceCatalog);

    await catalog.runOverWorkspace();

    await expect(catalog.loadRepos()).resolves.not.toContain('https://github.com/zyplux/zyplux');
  });

  test('1.3.3 reports dependencies it could not resolve to a repo', async ({ catalog, network }) => {
    network.otherwise(resolveFromWorkspaceCatalog);

    await catalog.runOverWorkspace();

    expect(catalog.unresolvedNames('npm')).toContain('eslint');
    expect(catalog.unresolvedNames('pypi')).toContain('pytest');
  });
});

describe('1.4 skipping manifest files that fail to parse', () => {
  test('1.4.1 skips package.json and pyproject.toml files that fail to parse, keeping the rest', async ({
    catalog,
    network,
  }) => {
    await catalog.writeManifest('bad-toml/pyproject.toml', '[project\nname = "should-not-parse"\n');
    await catalog.writeManifest(
      'empty-name/pyproject.toml',
      '[project]\nname = ""\n\n[project.urls]\nSource = "https://github.com/emptyname/repo"\n',
    );
    await catalog.writeManifest('good/package.json', npmManifest('depa', 'depb', 'depc'));
    await catalog.writeManifest(
      'no-name/pyproject.toml',
      '[project.urls]\nSource = "https://github.com/noname/repo"\n',
    );
    await catalog.writeManifest('package.json', '{ "name": "should-not-parse", ');
    network.otherwise(
      depsDevRouteFor(
        new Map([
          ['npm:depa', 'github.com/noname/repo'],
          ['npm:depb', 'github.com/emptyname/repo'],
          ['npm:depc', 'github.com/survivor/repo'],
        ]),
      ),
    );

    await catalog.run();

    await expect(catalog.loadRepos()).resolves.toEqual(['https://github.com/survivor/repo']);
  });
});
