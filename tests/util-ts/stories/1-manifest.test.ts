import { describe, expect, test } from '#fixtures';

const byLocale = (left: string, right: string) => left.localeCompare(right);

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
  test('1.1.1 parses package json text into a typed manifest and strips unknown keys', ({
    packageJsonSchema,
    parseJson,
  }) => {
    const manifest = parseJson(packageJsonText, packageJsonSchema);

    expect(manifest).toEqual({
      dependencies: { zod: 'catalog:' },
      name: '@scope/app',
      workspaces: { catalog: { react: '^19' } },
    });
    expect(manifest).not.toHaveProperty('scripts');
  });

  test('1.1.2 tolerates the array form of workspaces', ({ packageJsonSchema, parseJson }) => {
    const manifest = parseJson('{ "workspaces": ["packages/*"] }', packageJsonSchema);

    expect(manifest).toEqual({ workspaces: ['packages/*'] });
  });

  test('1.1.3 parses pyproject toml text with pep 621 and pep 735 dependency sections and strips unknown keys', ({
    parseToml,
    pyProjectSchema,
  }) => {
    const manifest = parseToml(pyprojectTomlText, pyProjectSchema);

    expect(manifest).toEqual({
      'dependency-groups': { dev: ['ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28'], name: 'app', 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });
    expect(manifest).not.toHaveProperty('build-system');
  });
});

describe('1.2 collecting and normalizing dependency names from a manifest', () => {
  test('1.2.1 collects npm catalog and dependency field names while skipping workspace local specs', ({
    npmDependencyNames,
    packageJsonSchema,
  }) => {
    const manifest = packageJsonSchema.parse({
      dependencies: { '@scope/local': 'workspace:*', react: '^19' },
      devDependencies: { vitest: 'catalog:' },
      workspaces: { catalog: { zod: 'catalog:' }, catalogs: { build: { esbuild: '^0.21' } } },
    });

    expect(npmDependencyNames(manifest).toSorted(byLocale)).toEqual(['esbuild', 'react', 'vitest', 'zod']);
  });

  test('1.2.2 collects python requirement names across every section while dropping python itself', ({
    pyProjectSchema,
    pythonRequirementNames,
  }) => {
    const manifest = pyProjectSchema.parse({
      'dependency-groups': { dev: ['Ruff>=0.1'] },
      project: { dependencies: ['httpx>=0.28', 'python>=3.12'], 'optional-dependencies': { http: ['urllib3'] } },
      tool: { uv: { 'dev-dependencies': ['pytest>=8'] } },
    });

    expect(pythonRequirementNames(manifest).toSorted(byLocale)).toEqual(['httpx', 'pytest', 'ruff', 'urllib3']);
  });

  type NormalizeCase = [shape: string, requirement: string, canonical: string | undefined];

  const normalizeCases: NormalizeCase[] = [
    [
      '3 normalizes an underscored requirement name into its pep 503 canonical form',
      'Flask_SQLAlchemy',
      'flask-sqlalchemy',
    ],
    ['4 normalizes a dotted requirement name with a version specifier', 'ruamel.yaml >= 0.18', 'ruamel-yaml'],
    ['5 returns undefined when no package name can be parsed from a requirement', '\t \n', undefined],
  ];

  test.for(normalizeCases)('1.2.%s', ([, requirement, canonical], { normalizePythonName }) => {
    expect(normalizePythonName(requirement)).toBe(canonical);
  });
});

describe("1.3 resolving a manifest's repository url", () => {
  test.for([
    [
      '1 reads the url from a string repository field',
      'https://github.com/owner/repo',
      'https://github.com/owner/repo',
    ],
    [
      '2 reads the url from an object repository field',
      { url: 'git+https://github.com/owner/repo.git' },
      'git+https://github.com/owner/repo.git',
    ],
    ['3 returns undefined when no repository is declared', undefined, undefined],
  ] as const)('1.3.%s', ([, repository, expected], { repositoryUrl }) => {
    expect(repositoryUrl(repository)).toBe(expected);
  });
});

describe('1.4 discovering manifests tracked by git', () => {
  test('1.4.1 lists tracked manifests under the repo and excludes ignored paths', async ({
    findManifests,
    workspaceRoot,
  }) => {
    const manifests = await findManifests(workspaceRoot);

    expect({
      allAreManifestFiles: manifests.every(file => file.endsWith('package.json') || file.endsWith('pyproject.toml')),
      excludesNodeModules: manifests.every(file => !file.includes('/node_modules/')),
      includesUtilPackageJson: manifests.some(file => file.endsWith('/packages/util-ts/package.json')),
    }).toEqual({ allAreManifestFiles: true, excludesNodeModules: true, includesUtilPackageJson: true });
  });

  test('1.4.2 discovers manifests across nested repositories when the directory itself is outside any repository', async ({
    createNestedGitRepos,
    findManifests,
    tempDir,
  }) => {
    const expectedManifests = await createNestedGitRepos(tempDir.path);

    const manifests = await findManifests(tempDir.path);

    expect(manifests.toSorted(byLocale)).toEqual(expectedManifests.toSorted(byLocale));
  });
});
