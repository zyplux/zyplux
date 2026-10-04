import { describe, expect, test } from './architecture.ts';

const workspace = {
  'package.json': '{"name":"sample","private":true}',
  'packages/consumer/package.json': '{"name":"@sample/consumer","exports":{"./entry":"./src/entry.ts"}}',
  'packages/provider/package.json':
    '{"name":"@sample/provider","exports":{"./api":"./src/api.ts","./contracts":"./src/contracts.ts"}}',
  'packages/provider/src/api.ts': 'export type Response = string; export const fetchResponse = () => "ready";',
  'packages/provider/src/contracts.ts': 'export type Request = string;',
  'pnpm-workspace.yaml': 'packages: [packages/*]',
};

describe('22.1 enforcing declared dependency direction', () => {
  test.for([
    ['1 a normal runtime import', 'import { fetchResponse } from "@sample/provider/api";'],
    ['2 a type-only import', 'import type { Response } from "@sample/provider/api";'],
    ['3 a resolved alias', 'import { fetchResponse } from "@provider/api";'],
    ['4 a dynamic import', 'const load = () => import("@sample/provider/api");'],
    ['5 a type query', 'export type API = typeof import("@sample/provider/api");'],
  ])('22.1.%s', async ([, source], { lintArchitecture }) => {
    const reports = await lintArchitecture({
      ...workspace,
      'cerberus.toml': '[architecture.dependencies]\n"@sample/consumer"=[]',
      'packages/consumer/src/entry.ts': source ?? '',
    });
    expect(reports.map(report => report.message)).toContain(
      '@sample/consumer cannot depend on @sample/provider; this reverses the declared ownership direction.',
    );
  });
});

describe('22.2 preserving type ownership', () => {
  test.for([
    ['1 public API used only for types', 'import type { Response } from "@sample/provider/api";'],
    ['2 hidden implementation types', 'import type { Secret } from "@sample/provider/private";'],
    ['3 a relative implementation type', 'import type { Response } from "../../provider/src/api.ts";'],
  ])('22.2.%s', async ([, source], { lintArchitecture }) => {
    const reports = await lintArchitecture({
      ...workspace,
      'packages/consumer/src/entry.ts': source ?? '',
      'packages/provider/src/private.ts': 'export type Secret = string;',
    });
    expect(reports.map(report => report.messageId)).toEqual(['ownership']);
  });

  test('22.2.4 public options accompany an API used by the consumer', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture({
      ...workspace,
      'packages/consumer/src/entry.ts':
        'import { fetchResponse, type Response } from "@sample/provider/api"; export const response: Response = fetchResponse();',
    });
    expect(reports).toEqual([]);
  });

  test('22.2.5 domain contract types are shared without implementation imports', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture({
        ...workspace,
        'packages/consumer/src/entry.ts':
          'import type { Request } from "@sample/provider/contracts"; export type Query = Request;',
      }),
    ).toEqual([]);
  });

  test('22.2.6 ordinary relative imports retain their existing semantics', async ({ lintArchitecture }) => {
    expect(
      await lintArchitecture({
        ...workspace,
        'packages/consumer/src/entry.ts':
          'import { fetchResponse } from "../../provider/src/api.ts"; export const response = fetchResponse();',
      }),
    ).toEqual([]);
  });

  test('22.2.7 a resolved private alias cannot borrow the public root entry', async ({ lintArchitecture }) => {
    const reports = await lintArchitecture({
      ...workspace,
      'packages/consumer/src/entry.ts':
        'import { fetchResponse } from "@sample/provider"; import type { Secret } from "#private"; export const response: Secret = fetchResponse();',
      'packages/provider/package.json': '{"name":"@sample/provider","exports":{".":"./src/api.ts"}}',
      'packages/provider/src/private.ts': 'export type Secret = string;',
    });
    expect(reports.map(report => report.message)).toEqual([expect.stringContaining('not a public package entry')]);
  });
});
