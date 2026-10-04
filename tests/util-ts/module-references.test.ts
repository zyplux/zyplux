import { collectModuleReferences } from '@zyplux/util/module-references';
import ts from 'typescript';
import { expect, test } from 'vitest';

test.each([
  ["import 'provider';", false, false, false],
  ["import Default from 'provider';", false, true, false],
  ["import * as namespace from 'provider';", false, true, false],
  ["export * from 'provider';", false, true, false],
  ["export * as namespace from 'provider';", false, true, false],
  ["export type * from 'provider';", true, false, true],
] as const)('module references describe %s', (source, hasTypeBindings, hasValueBindings, isTypeOnly) => {
  const sourceFile = ts.createSourceFile('caller.ts', source, ts.ScriptTarget.Latest, true);
  expect(collectModuleReferences(sourceFile)).toEqual([
    { filePath: 'caller.ts', hasTypeBindings, hasValueBindings, isTypeOnly, line: 1, specifier: 'provider' },
  ]);
});

test('declarations and local re-exports do not create module references', () => {
  const sourceFile = ts.createSourceFile(
    'local.ts',
    'const local = true; export { local };',
    ts.ScriptTarget.Latest,
    true,
  );
  expect(collectModuleReferences(sourceFile)).toEqual([]);
});
