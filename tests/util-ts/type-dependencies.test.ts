import { collectModuleReferences } from '@zyplux/util/module-references';
import { findTypeDependencyViolations } from '@zyplux/util/type-dependencies';
import path from 'node:path';
import ts from 'typescript';
import { expect, test } from 'vitest';

const PACKAGES = [
  { directory: 'apps/client', exports: { '.': './src/index.ts' }, name: '@example/client' },
  { directory: 'packages/component', exports: { '.': './src/index.ts' }, name: '@example/component' },
  {
    directory: 'packages/domain-model',
    exports: { './contracts': './src/contracts.ts' },
    name: '@example/domain-model',
  },
];

const checkTypeDependencies = (sources: Record<string, string>, packages = PACKAGES) =>
  findTypeDependencyViolations({
    imports: Object.entries(sources).flatMap(([filePath, source]) =>
      collectModuleReferences(ts.createSourceFile(filePath, source, ts.ScriptTarget.Latest, true)),
    ),
    packages,
    sharedTypeSurfaces: new Set(['contracts']),
  });

test('borrowing types is rejected across import forms and type-module locations', () => {
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

test('local types, shared contracts, and public API types preserve their owners', () => {
  expect(
    checkTypeDependencies({
      'apps/client/src/caller.ts': "import { start, type Options } from '@example/component';",
      'apps/client/src/types.ts': "export type { Options } from '@example/component';",
      'packages/component/src/store.ts': "import type { LoadResult } from './loader.ts';",
      'packages/component/src/types.ts': "import type { Order } from '@example/domain-model/contracts';",
    }),
  ).toEqual([]);
});

test('using an API does not permit reaching into its private modules', () => {
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

test('relative and absolute host paths identify the same package owners', () => {
  for (const packages of [PACKAGES, PACKAGES.map(pkg => ({ ...pkg, directory: path.resolve(pkg.directory) }))]) {
    for (const filePath of ['apps/client/src/types.ts', path.resolve('apps/client/src/types.ts')]) {
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
