import { describe, expect, test } from './architecture.ts';

const workspace = {
  'package.json': '{"name":"sample","private":true}',
  'packages/consumer/package.json': '{"name":"@sample/consumer","exports":{"./entry":"./src/entry.ts"}}',
  'packages/provider/package.json':
    '{"name":"@sample/provider","exports":{"./api":"./src/api.ts","./contracts":"./src/contracts.ts","./interfaces":"./src/interfaces.ts"}}',
  'packages/provider/src/api.ts': 'export type Response = string; export const fetchResponse = () => "ready";',
  'packages/provider/src/contracts.ts': 'export type Request = string;',
  'packages/provider/src/interfaces.ts': 'export type Connection = string;',
  'packages/provider/src/private.ts': 'export type Secret = string;',
  'pnpm-workspace.yaml': 'packages: [packages/*]',
};

describe('22.1 using public package type exports', () => {
  test.for([
    ['1 rejects a private type import', 'import type { Secret } from "@sample/provider/private";'],
    ['2 rejects an inline private type import', 'import { type Secret } from "@sample/provider/private";'],
    ['3 rejects a private type re-export', 'export type { Secret } from "@sample/provider/private";'],
    ['4 rejects an inline private type re-export', 'export { type Secret } from "@sample/provider/private";'],
    ['5 rejects a private import type expression', 'type Secret = import("@sample/provider/private").Secret;'],
    [
      '6 rejects a direct path to an exported source file',
      'import type { Response } from "../../provider/src/api.ts";',
    ],
    ['7 rejects a resolved private alias', 'import type { Secret } from "#private";'],
  ])('22.1.%s', async ([, source = ''], { lintArchitecture }) => {
    const reports = await lintArchitecture({ ...workspace, 'packages/consumer/src/entry.ts': source });
    expect(reports.map(report => ({ line: report.line, messageId: report.messageId, ruleId: report.ruleId }))).toEqual([
      { line: 1, messageId: 'packageExport', ruleId: '@zyplux/use-package-type-exports' },
    ]);
  });

  test('22.1.8 public type-only imports and re-exports pass the export rule', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture({
        ...workspace,
        'packages/consumer/src/entry.ts':
          'import type { Response } from "@sample/provider/api"; export type { Response as Reply } from "@sample/provider/api";',
      }),
    ).toEqual([]);
  });

  test('22.1.9 imports within the provider can reach its internal files', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture(
        { ...workspace, 'packages/provider/src/internal.ts': 'import type { Secret } from "./private.ts";' },
        'use-package-type-exports',
        [],
        'packages/provider/src/internal.ts',
      ),
    ).toEqual([]);
  });

  test('22.1.10 a public value import does not authorize a private alias', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture({
      ...workspace,
      'packages/consumer/src/entry.ts':
        'import { fetchResponse } from "@sample/provider";\nimport type { Secret } from "#private";',
      'packages/provider/package.json': '{"name":"@sample/provider","exports":{".":"./src/api.ts"}}',
    });
    expect(reports).toMatchObject([{ line: 2, messageId: 'packageExport' }]);
  });

  test('22.1.11 value-only references are outside the type export rule', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture({
        ...workspace,
        'packages/consumer/src/entry.ts': 'import { fetchResponse } from "../../provider/src/api.ts";',
      }),
    ).toEqual([]);
  });
});

describe('22.2 rejecting type-only implementation dependencies', () => {
  test.for([
    ['1 rejects a type-only API import', 'import type { Response } from "@sample/provider/api";'],
    ['2 rejects an inline type-only API import', 'import { type Response } from "@sample/provider/api";'],
    ['3 rejects a type-only API re-export', 'export type { Response } from "@sample/provider/api";'],
    ['4 rejects an inline type-only API re-export', 'export { type Response } from "@sample/provider/api";'],
    ['5 rejects an API import type expression', 'type Response = import("@sample/provider/api").Response;'],
  ])('22.2.%s', async ([, source = ''], { lintArchitecture }) => {
    const reports = await lintArchitecture(
      { ...workspace, 'packages/consumer/src/entry.ts': source },
      'no-type-only-dependencies',
    );
    expect(reports.map(report => ({ messageId: report.messageId, ruleId: report.ruleId }))).toEqual([
      { messageId: 'typeOnlyDependency', ruleId: '@zyplux/no-type-only-dependencies' },
    ]);
  });

  test('22.2.6 public API types can accompany a value import in another consumer file', async ({
    lintArchitecture,
  }) => {
    expect(
      await lintArchitecture(
        {
          ...workspace,
          'packages/consumer/src/caller.ts': 'import { fetchResponse } from "@sample/provider/api";',
          'packages/consumer/src/entry.ts': 'import type { Response } from "@sample/provider/api";',
        },
        'no-type-only-dependencies',
      ),
    ).toEqual([]);
  });

  test('22.2.7 public contracts and interfaces need no implementation import', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture(
        {
          ...workspace,
          'packages/consumer/src/entry.ts':
            'import type { Request } from "@sample/provider/contracts"; import type { Connection } from "@sample/provider/interfaces";',
        },
        'no-type-only-dependencies',
      ),
    ).toEqual([]);
  });

  test('22.2.8 private entries belong to the package export rule', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture(
        { ...workspace, 'packages/consumer/src/entry.ts': 'import type { Secret } from "#private";' },
        'no-type-only-dependencies',
      ),
    ).toEqual([]);
  });

  test('22.2.9 a private value import cannot establish a public API dependency', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture(
      {
        ...workspace,
        'packages/consumer/src/entry.ts':
          'import { fetchResponse } from "../../provider/src/api.ts"; import type { Response } from "@sample/provider/api";',
      },
      'no-type-only-dependencies',
    );
    expect(reports).toMatchObject([{ messageId: 'typeOnlyDependency' }]);
  });

  test('22.2.10 both rules report their own restriction without duplicate diagnostics', async ({
    lintArchitecture,
  }) => {
    const reports = await lintArchitecture(
      {
        ...workspace,
        'packages/consumer/src/entry.ts':
          'import type { Secret } from "#private";\nimport type { Response } from "@sample/provider/api";',
      },
      ['use-package-type-exports', 'no-type-only-dependencies'],
    );
    expect(reports.map(report => ({ line: report.line, ruleId: report.ruleId }))).toEqual([
      { line: 1, ruleId: '@zyplux/use-package-type-exports' },
      { line: 2, ruleId: '@zyplux/no-type-only-dependencies' },
    ]);
  });
});
