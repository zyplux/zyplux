import { expect, test } from './compiler.ts';

test('11.1.1 export maps preserve conditions, arrays, wildcards, and blocked entries', async ({
  buildExportMap,
  hasPublicExport,
  listExportTargets,
  listWorkspacePackages,
  tempDir,
}) => {
  expect(buildExportMap({ default: './dist/index.js', import: './src/index.ts' })).toEqual({
    '.': { default: './dist/index.js', import: './src/index.ts' },
  });
  await tempDir.write('package.json', '{"name":"library","exports":{"./api/*":["./src/*.ts"],"./api/private":null}}');
  const exports = listWorkspacePackages(tempDir.path)[0]?.exports;
  expect(listExportTargets(exports)).toEqual(['./src/*.ts']);
  expect(hasPublicExport(exports, './api/public')).toBe(true);
  expect(hasPublicExport(exports, './api/private')).toBe(false);
  expect(hasPublicExport(exports, '.')).toBe(false);
});

test('11.1.2 nested packages own their files ahead of the root package', ({ findPackageOwner, resolvePath }) => {
  const packages = [
    { directory: resolvePath('.'), name: 'root' },
    { directory: resolvePath('packages/nested'), name: 'nested' },
  ];
  expect(findPackageOwner(resolvePath('packages/nested/src/api.ts'), packages)?.name).toBe('nested');
  expect(findPackageOwner(resolvePath('scripts/build.ts'), packages)?.name).toBe('root');
  expect(findPackageOwner(resolvePath('/outside'), packages)).toBeUndefined();
});

test('11.2.1 workspace discovery honors exclusions and single-package defaults', async ({
  listWorkspacePackages,
  tempDir,
}) => {
  await tempDir.write('package.json', '{"name":"root"}');
  await tempDir.write('pnpm-workspace.yaml', 'catalog: {}');
  expect(listWorkspacePackages(tempDir.path).map(({ name }) => name)).toEqual(['root']);
  await tempDir.write('packages/library/package.json', '{"name":"library"}');
  await tempDir.write('packages/private/package.json', '{"name":"private"}');
  await tempDir.write('pnpm-workspace.yaml', 'packages: ["packages/*", "!packages/private"]');
  expect(listWorkspacePackages(tempDir.path).map(({ name }) => name)).toEqual(['library']);
});

test('11.2.2 architecture loading supplies defaults and validates declared scope', async ({
  loadArchitecture,
  tempDir,
}) => {
  expect(loadArchitecture(tempDir.path)).toEqual({ applications: [], dependencies: {} });
  await tempDir.write('cerberus.toml', '[architecture.dependencies]\nfoundation=[]');
  expect(loadArchitecture(tempDir.path).dependencies).toEqual({ foundation: [] });
  await tempDir.write('cerberus.toml', '[architecture.dependencies]\nfoundation="wrong"');
  expect(() => loadArchitecture(tempDir.path)).toThrow();
  await tempDir.write('cerberus.toml', '[architecture]\ndepedencies={}');
  expect(() => loadArchitecture(tempDir.path)).toThrow();
});

test('11.1.3 export patterns prefer the longest static prefix when a wildcard is blocked', async ({
  hasPublicExport,
  listWorkspacePackages,
  tempDir,
}) => {
  await tempDir.write('package.json', '{"name":"library","exports":{"./api/*":null,"./*/public":"./src/*.ts"}}');
  expect(hasPublicExport(listWorkspacePackages(tempDir.path)[0]?.exports, './api/public')).toBe(false);
});
