import { expect, test } from './compiler.ts';

test.for([
  ['1 represents side-effect imports', "import 'provider';", false, false, false],
  ['2 represents default imports', "import Default from 'provider';", false, true, false],
  ['3 represents namespace imports', "import * as namespace from 'provider';", false, true, false],
  ['4 represents re-exports', "export * from 'provider';", false, true, false],
  ['5 represents namespace re-exports', "export * as namespace from 'provider';", false, true, false],
  ['6 represents type-only re-exports', "export type * from 'provider';", true, false, true],
] as const)('9.1.%s', ([, source, hasTypeBindings, hasValueBindings, isTypeOnly], { collectReferences }) => {
  expect(collectReferences(source)).toEqual([
    { filePath: 'caller.ts', hasTypeBindings, hasValueBindings, isTypeOnly, line: 1, specifier: 'provider' },
  ]);
});

test('9.2.1 declarations and local re-exports do not create module references', ({ collectReferences }) => {
  expect(collectReferences('const local = true; export { local };', 'local.ts')).toEqual([]);
});
