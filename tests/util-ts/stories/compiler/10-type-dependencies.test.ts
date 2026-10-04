import { expect, test } from './compiler.ts';

test('10.1.1 borrowing types is rejected across import forms and type-module locations', ({
  checkTypeDependencies,
}) => {
  for (const statement of [
    "import type { Options } from '@example/component';",
    "import { type Options } from '@example/component';",
    "export type { Options } from '@example/component';",
    "export { type Options } from '@example/component';",
  ]) {
    const violations = checkTypeDependencies({ 'apps/client/src/types.ts': statement });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('apps/client/src/types.ts:1');
    expect(violations[0]).toContain('implementation package is used only for types');
  }
});

test('10.1.2 local types, shared contracts, and public API types preserve their owners', ({
  checkTypeDependencies,
}) => {
  expect(
    checkTypeDependencies({
      'apps/client/src/caller.ts': "import { start, type Options } from '@example/component';",
      'apps/client/src/types.ts': "export type { Options } from '@example/component';",
      'packages/component/src/store.ts': "import type { LoadResult } from './loader.ts';",
      'packages/component/src/types.ts': "import type { Order } from '@example/domain-model/contracts';",
    }),
  ).toEqual([]);
});

test('10.1.3 using an API does not permit reaching into its private modules', ({ checkTypeDependencies }) => {
  for (const statement of [
    "import type { Options } from '@example/component/src/private';",
    "import { start, type Options } from '@example/component/src/private';",
    "import type { Options } from '../../../packages/component/src/private';",
  ]) {
    const violations = checkTypeDependencies({
      'apps/client/src/caller.ts': "import { start } from '@example/component';",
      'apps/client/src/types.ts': statement,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('not a public package entry');
  }
});

test('10.1.4 relative and absolute host paths identify the same package owners', ({
  checkTypeDependencies,
  packages: packageFixtures,
  resolvePath,
}) => {
  for (const packages of [
    packageFixtures,
    packageFixtures.map(pkg => ({ ...pkg, directory: resolvePath(pkg.directory) })),
  ]) {
    for (const filePath of ['apps/client/src/types.ts', resolvePath('apps/client/src/types.ts')]) {
      expect(
        checkTypeDependencies(
          {
            [filePath]: [
              "import type { Options } from '@example/component';",
              "import type { PrivateOptions } from '../../../packages/component/src/private';",
            ].join('\n'),
          },
          packages,
        ),
      ).toEqual([
        expect.stringContaining('implementation package is used only for types'),
        expect.stringContaining('not a public package entry'),
      ]);
    }
  }
});
