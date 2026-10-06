import { expect, test } from './compiler.ts';

test('10.1.1 borrowing types is rejected across import forms and type-module locations', ({ checkPackageTypes }) => {
  for (const statement of [
    "import type { Options } from '@example/component';",
    "import { type Options } from '@example/component';",
    "export type { Options } from '@example/component';",
    "export { type Options } from '@example/component';",
  ]) {
    const { typeOnlyDependencies, unexportedTypes } = checkPackageTypes({ 'apps/client/src/types.ts': statement });
    expect(unexportedTypes).toEqual([]);
    expect(typeOnlyDependencies).toMatchObject([
      {
        consumer: { name: '@example/client' },
        filePath: 'apps/client/src/types.ts',
        line: 1,
        provider: { name: '@example/component' },
        specifier: '@example/component',
      },
    ]);
  }
});

test('10.1.2 local types, shared contracts, and public API types preserve their owners', ({ checkPackageTypes }) => {
  expect(
    checkPackageTypes({
      'apps/client/src/caller.ts': "import { start, type Options } from '@example/component';",
      'apps/client/src/types.ts': "export type { Options } from '@example/component';",
      'packages/component/src/store.ts': "import type { LoadResult } from './loader.ts';",
      'packages/component/src/types.ts': "import type { Order } from '@example/domain-model/contracts';",
    }),
  ).toEqual({ typeOnlyDependencies: [], unexportedTypes: [] });
});

test('10.1.3 using an API does not permit reaching into its private modules', ({ checkPackageTypes }) => {
  for (const statement of [
    "import type { Options } from '@example/component/src/private';",
    "import { start, type Options } from '@example/component/src/private';",
    "import type { Options } from '../../../packages/component/src/private';",
  ]) {
    const { typeOnlyDependencies, unexportedTypes } = checkPackageTypes({
      'apps/client/src/caller.ts': "import { start } from '@example/component';",
      'apps/client/src/types.ts': statement,
    });
    expect(typeOnlyDependencies).toEqual([]);
    expect(unexportedTypes).toMatchObject([
      { filePath: 'apps/client/src/types.ts', line: 1, provider: { name: '@example/component' } },
    ]);
  }
});

test('10.1.4 relative and absolute host paths identify the same package owners', ({
  checkPackageTypes,
  packages: packageFixtures,
  resolvePath,
}) => {
  for (const packages of [
    packageFixtures,
    packageFixtures.map(pkg => ({ ...pkg, directory: resolvePath(pkg.directory) })),
  ]) {
    for (const filePath of ['apps/client/src/types.ts', resolvePath('apps/client/src/types.ts')]) {
      expect(
        checkPackageTypes(
          {
            [filePath]: [
              "import type { Options } from '@example/component';",
              "import type { PrivateOptions } from '../../../packages/component/src/private';",
            ].join('\n'),
          },
          packages,
        ),
      ).toMatchObject({
        typeOnlyDependencies: [{ filePath, line: 1, specifier: '@example/component' }],
        unexportedTypes: [{ filePath, line: 2, specifier: '../../../packages/component/src/private' }],
      });
    }
  }
});
