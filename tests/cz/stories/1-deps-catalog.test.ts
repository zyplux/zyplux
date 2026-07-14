import type { Catalog } from '#fixtures';

import { describe, expect, test } from '#fixtures';

const npmManifest = (name: string, dependencies: Record<string, string>) => JSON.stringify({ dependencies, name });

const seedWorkspace = async (catalog: Catalog) => {
  await catalog.writeManifest('packages/widgets/package.json', npmManifest('@scratch/widgets', { zod: '^3' }));
  await catalog.writeManifest(
    'apps/web/package.json',
    npmManifest('@scratch/web', { '@scratch/widgets': '^1.0.0', eslint: '^9', zod: '^3' }),
  );
  await catalog.writeManifest(
    'libs/toolkit/pyproject.toml',
    '[project]\nname = "scratch-toolkit"\ndependencies = ["pytest"]\n',
  );
  await catalog.writeManifest(
    'apps/service/pyproject.toml',
    '[project]\nname = "scratch-service"\ndependencies = ["scratch-toolkit", "ruff", "pytest"]\n\n' +
      '[dependency-groups]\ndev = ["pyrefly"]\n',
  );
};

type ScanCase = [shape: string, packageRegistry: 'npm' | 'pypi', expected: string[]];

const scanCases: ScanCase[] = [
  ['1 collects deduplicated npm dependency names', 'npm', ['eslint', 'zod']],
  ['2 collects deduplicated pypi dependency names', 'pypi', ['pyrefly', 'pytest', 'ruff']],
];

describe('1.1 scanning workspace manifests for declared dependency names', () => {
  test.for(scanCases)('1.1.%s', async ([, packageRegistry, expected], { catalog }) => {
    await seedWorkspace(catalog);

    await catalog.run();

    expect(catalog.unresolvedNames(packageRegistry)).toContainExactElementsInAnyOrder(expected);
  });
});

type ExcludeCase = [shape: string, packageRegistry: 'npm' | 'pypi', excludedName: string];

const excludeCases: ExcludeCase[] = [
  ['1 excludes an internal npm package from its own dependency list', 'npm', '@scratch/widgets'],
  ['2 excludes an internal pypi package from its own dependency list', 'pypi', 'scratch-toolkit'],
];

describe('1.2 excluding internal workspace packages from declared dependency names', () => {
  test.for(excludeCases)('1.2.%s', async ([, packageRegistry, excludedName], { catalog }) => {
    await seedWorkspace(catalog);

    await catalog.run();

    expect(catalog.unresolvedNames(packageRegistry)).not.toContain(excludedName);
  });
});

type ResolveCase = [
  shape: string,
  manifestPath: string,
  manifestText: string,
  stub: ((catalog: Catalog) => void) | undefined,
  expectedRepos: string[],
  expectedUnresolvedNpm?: string[],
];

const resolveCases: ResolveCase[] = [
  [
    '1 resolves a package to its source repo via deps dev',
    'package.json',
    npmManifest('scratch-app', { react: '*' }),
    catalog => {
      catalog.stubDepsDev({ 'npm:react': 'github.com/facebook/react' });
    },
    ['https://github.com/facebook/react'],
  ],
  [
    '2 falls back to the npm registry when deps dev has no source repo',
    'package.json',
    npmManifest('scratch-app', { react: '*' }),
    catalog => {
      catalog.stubNpmRegistry({ react: 'github.com/facebook/react' });
    },
    ['https://github.com/facebook/react'],
  ],
  [
    '3 falls back to pypi project urls when deps dev has no source repo',
    'pyproject.toml',
    '[project]\nname = "scratch-app"\ndependencies = ["requests"]\n',
    catalog => {
      catalog.stubPypiRegistry({ requests: 'github.com/psf/requests' });
    },
    ['https://github.com/psf/requests'],
  ],
  [
    '4 reports the dependency as unresolved when no source repo is found anywhere',
    'package.json',
    npmManifest('scratch-app', { 'does-not-exist': '*' }),
    undefined,
    [],
    ['does-not-exist'],
  ],
  [
    '5 falls back to a deps dev links entry when there is no related project',
    'package.json',
    npmManifest('scratch-app', { zod: '*' }),
    catalog => {
      catalog.stubDepsDev({ 'npm:zod': { repo: 'github.com/colinhacks/zod', via: 'links' } });
    },
    ['https://github.com/colinhacks/zod'],
  ],
];

describe('1.3 resolving a dependency name to its source repository', () => {
  test.for(resolveCases)(
    '1.3.%s',
    async ([, manifestPath, manifestText, stub, expectedRepos, expectedUnresolvedNpm], { catalog }) => {
      await catalog.writeManifest(manifestPath, manifestText);
      stub?.(catalog);

      await catalog.run();

      if (expectedUnresolvedNpm !== undefined) {
        expect(catalog.unresolvedNames('npm')).toEqual(expectedUnresolvedNpm);
      }
      await expect(catalog.loadRepos()).resolves.toEqual(expectedRepos);
    },
  );
});

const seedResolvableWorkspace = async (catalog: Catalog) => {
  await catalog.writeManifest(
    'packages/toolkit/package.json',
    JSON.stringify({ name: '@scratch/toolkit', repository: 'https://github.com/scratch-org/toolkit' }),
  );
  await catalog.writeManifest(
    'apps/web/package.json',
    npmManifest('@scratch/web', {
      eslint: '^9',
      'legacy-toolkit-mirror': '^1.0.0',
      react: '^19',
      'react-dom': '^19',
      zod: '^3',
    }),
  );
  catalog.stubDepsDev({
    'npm:legacy-toolkit-mirror': 'github.com/scratch-org/toolkit',
    'npm:react': 'github.com/facebook/react',
    'npm:react-dom': 'github.com/facebook/react',
    'npm:zod': 'github.com/colinhacks/zod',
  });
};

type ResolvedWorkspaceCase = [shape: string, assertResolved: (catalog: Catalog) => Promise<void> | void];

const resolvedWorkspaceCases: ResolvedWorkspaceCase[] = [
  [
    '1 collects deduplicated source repos for resolved dependencies',
    async catalog => {
      const repos = await catalog.loadRepos();
      expect(repos).toContainExactElementsInAnyOrder([
        'https://github.com/colinhacks/zod',
        'https://github.com/facebook/react',
      ]);
    },
  ],
  [
    '2 excludes repos that belong to the scanned workspace itself',
    async catalog => {
      await expect(catalog.loadRepos()).resolves.not.toContain('https://github.com/scratch-org/toolkit');
    },
  ],
  [
    '3 reports dependencies it could not resolve to a repo',
    catalog => {
      expect(catalog.unresolvedNames('npm')).toContain('eslint');
    },
  ],
];

describe('1.4 collecting the external repos a workspace depends on', () => {
  test.for(resolvedWorkspaceCases)('1.4.%s', async ([, assertResolved], { catalog }) => {
    await seedResolvableWorkspace(catalog);

    await catalog.run();

    await assertResolved(catalog);
  });
});

describe('1.5 skipping manifest files that fail to parse', () => {
  test('1.5.1 skips package.json and pyproject.toml files that fail to parse, keeping the rest', async ({
    catalog,
  }) => {
    await catalog.writeManifest('bad-toml/pyproject.toml', '[project\nname = "should-not-parse"\n');
    await catalog.writeManifest(
      'empty-name/pyproject.toml',
      '[project]\nname = ""\n\n[project.urls]\nSource = "https://github.com/emptyname/repo"\n',
    );
    await catalog.writeManifest('good/package.json', npmManifest('good', { depa: '*', depb: '*', depc: '*' }));
    await catalog.writeManifest(
      'no-name/pyproject.toml',
      '[project.urls]\nSource = "https://github.com/noname/repo"\n',
    );
    await catalog.writeManifest('package.json', '{ "name": "should-not-parse", ');
    catalog.stubDepsDev({
      'npm:depa': 'github.com/noname/repo',
      'npm:depb': 'github.com/emptyname/repo',
      'npm:depc': 'github.com/survivor/repo',
    });

    await catalog.run();

    await expect(catalog.loadRepos()).resolves.toEqual(['https://github.com/survivor/repo']);
  });
});
