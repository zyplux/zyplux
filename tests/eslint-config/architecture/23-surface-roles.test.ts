import { describe, expect, test } from './architecture.ts';

describe('23.1 requiring pure barrels', () => {
  test.for([
    ['1 accepts named and star re-exports', 'export { x } from "./x.ts"; export * from "./types.ts";', false],
    ['2 rejects a local declaration', 'export const x = 1;', true],
    ['3 rejects registration in the entry', 'import "./setup.ts";', true],
  ])('23.1.%s', async ([, source, hasFinding], { lintArchitecture }) => {
    const reports = await lintArchitecture(
      { 'packages/consumer/src/entry.ts': String(source) },
      'barrel-only-reexports',
    );
    expect(reports.map(report => report.messageId)).toEqual(hasFinding ? ['statement'] : []);
  });
});

describe('23.2 enforcing type-only modules', () => {
  test.for([
    ['1 accepts interfaces and aliases', 'export interface X { name: string } export type Y = string;', false],
    ['2 accepts inline type imports', 'import { type X } from "./types.ts"; export type { X };', false],
    ['3 rejects runtime imports', 'import { x } from "./x.ts";', true],
    ['4 rejects runtime constants', 'export const x = 1;', true],
    ['5 accepts type star re-exports', 'export type * from "./types.ts";', false],
  ])('23.2.%s', async ([, source, hasFinding], { lintArchitecture }) => {
    const reports = await lintArchitecture({ 'packages/consumer/src/entry.ts': String(source) }, 'type-only-modules');
    expect(reports.map(report => report.messageId)).toEqual(hasFinding ? ['runtime'] : []);
  });
});

describe('23.3 assigning constants their primitive role', () => {
  test.for([
    ['1 accepts primitive constants', 'export const label = "ready"; export const count = 1;', false],
    ['2 rejects object constants', 'export const config = { retries: 1 };', true],
    ['3 rejects mutable constants', 'export let count = 1;', true],
    ['4 rejects functions', 'export const getCount = () => 1;', true],
    ['5 rejects type exports', 'export type Count = number;', true],
    ['6 accepts primitive unions', 'export const flag: string | undefined = undefined;', false],
  ])('23.3.%s', async ([, source, hasFinding], { lintArchitecture }) => {
    const reports = await lintArchitecture(
      { 'packages/consumer/src/entry.ts': String(source) },
      'constants-only-primitives',
    );
    expect(reports.map(report => report.messageId)).toEqual(hasFinding ? ['nonPrimitive'] : []);
  });
});

describe('23.4 locating violations at the public export', () => {
  test('23.4.1 contracts report a runtime star re-export at its source line', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture(
      {
        'packages/consumer/src/entry.ts': 'export type Local = string;\n\nexport * from "./runtime.ts";',
        'packages/consumer/src/runtime.ts': 'export const invalid = () => {};',
      },
      'contracts-only-schemas',
    );
    expect(reports.map(({ line, messageId }) => ({ line, messageId }))).toEqual([
      { line: 3, messageId: 'nonSchemaExport' },
    ]);
  });

  test('23.4.2 constants reject type-only re-exports at the export specifier', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture(
      {
        'packages/consumer/src/entry.ts': 'export const ready = true;\nexport type { label } from "./runtime.ts";',
        'packages/consumer/src/runtime.ts': 'export const label = "ready";',
      },
      'constants-only-primitives',
    );
    expect(reports.map(({ line, messageId }) => ({ line, messageId }))).toEqual([
      { line: 2, messageId: 'nonPrimitive' },
    ]);
  });
});

describe('23.5 applying the shipped architecture scopes', () => {
  test.for(['types.ts', 'types.tsx', 'interfaces.tsx', 'interfaces/entry.tsx', 'types.mts', 'interfaces.cts'])(
    '23.5.1 rejects runtime declarations in %s',
    async (module, { lintArchitectureScopes }) => {
      const filename = `packages/consumer/src/${module}`;
      const reports = await lintArchitectureScopes(
        { [filename]: 'export const runtime = 1;' },
        'type-only-modules',
        filename,
      );
      expect(reports.map(report => report.messageId)).toEqual(['runtime']);
    },
  );

  test.for(['ts', 'tsx', 'mts', 'cts', 'js', 'jsx', 'mjs', 'cjs'])(
    '23.5.2 rejects declarations in an exported %s root',
    async (extension, { lintArchitectureScopes }) => {
      const filename = `packages/consumer/src/index.${extension}`;
      const reports = await lintArchitectureScopes(
        {
          [filename]: 'export const runtime = 1;',
          'package.json': '{"name":"sample"}',
          'packages/consumer/package.json': JSON.stringify({
            exports: { '.': `./src/index.${extension}` },
            name: 'consumer',
          }),
          'pnpm-workspace.yaml': 'packages: [packages/*]',
        },
        'barrel-only-reexports',
        filename,
      );
      expect(reports.map(report => report.messageId)).toEqual(['statement']);
    },
  );

  test.for([
    'tests/cluster-startup.test.ts',
    'tests/stories/api/example.test.ts',
    'apps/widget/tests/stories/example.test.tsx',
  ])('23.5.3 rejects direct helper imports in %s', async (filename, { lintArchitectureScopes }) => {
    const reports = await lintArchitectureScopes(
      { [filename]: 'import { helper } from "./helper.ts";' },
      'test-seam-only-imports',
      filename,
    );
    expect(reports.map(report => report.messageId)).toEqual(['moduleOutsideSeam']);
  });
});
