import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'contracts-only-schemas' });

const contractsFile = { filename: 'src/contracts.ts' };

type Case = [shape: string, code: string];
type LintFixtures = { lintRule: (code: string, options: typeof contractsFile) => unknown };
type MaybeReportCase = [shape: string, code: string, reportId?: string];

const runMaybeReportCase = ([, code, reportId]: MaybeReportCase, { lintRule }: LintFixtures) => {
  if (reportId === undefined) expect(lintRule(code, contractsFile)).toReportNothing();
  else expect(lintRule(code, contractsFile)).toReport(reportId);
};

describe('15.1 accepting schemas-only export surfaces', () => {
  test.for<Case>([
    [
      '15.1.1 allows a module of zod imports and exported schema consts',
      [
        "import * as z from 'zod';",
        'export const UserSchema = z.object({ id: z.string() });',
        'export const OrderSchema = z.object({ user: UserSchema });',
      ].join('\n'),
    ],
    [
      '15.1.2 allows type-only exports and type-only zod imports',
      [
        "import type { ZodType } from 'zod';",
        "import * as z from 'zod';",
        'export const IdSchema = z.string();',
        'export type Id = z.infer<typeof IdSchema>;',
        'export type AnySchema = ZodType;',
      ].join('\n'),
    ],
    [
      '15.1.3 allows non-exported schema consts and schema-building helpers feeding exported schemas',
      [
        "import * as z from 'zod';",
        'const BaseSchema = z.object({ id: z.string() });',
        'const withTimestamps = (schema: typeof BaseSchema) => schema.extend({ createdAt: z.string() });',
        'export const RecordSchema = withTimestamps(BaseSchema);',
      ].join('\n'),
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code, contractsFile)).toReportNothing();
  });
});

describe('15.2 rejecting non-schema exports', () => {
  test.for<Case>([
    [
      '15.2.1 flags an exported function',
      ["import * as z from 'zod';", 'export const parseId = (raw: string) => z.string().parse(raw);'].join('\n'),
    ],
    ['15.2.2 flags an exported plain object', 'export const config = { retries: 3 };'],
    ['15.2.3 flags an exported function declaration', 'export function parse() {}'],
    ['15.2.4 flags an exported class', 'export class Contract {}'],
    [
      '15.2.5 flags a non-schema value in an export specifier list while allowing schemas and type specifiers',
      [
        "import * as z from 'zod';",
        'const UserSchema = z.object({ id: z.string() });',
        'const limit = 3;',
        'type User = z.infer<typeof UserSchema>;',
        'export { UserSchema, limit, type User };',
      ].join('\n'),
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code, contractsFile)).toReport('nonSchemaExport');
  });
});

describe('15.3 opening imports while holding the export surface', () => {
  test.for<MaybeReportCase>([
    ['15.3.1 allows a node builtin import', "import path from 'node:path';"],
    ['15.3.2 allows a relative import', "import { helper } from './helper';"],
    ['15.3.3 allows a type-only import from an external module', "import type { Linter } from 'eslint';"],
    ['15.3.4 allows an import from an internal alias', "import { schema } from '#contracts/base';"],
    [
      '15.3.5 allows building and re-exporting a schema composed from an imported contracts schema',
      [
        "import * as z from 'zod';",
        "import { IdSchema } from '@zyplux/util/contracts';",
        'export const ProjectKeySchema = z.object({ projectKey: IdSchema });',
      ].join('\n'),
    ],
    [
      '15.3.6 allows building and re-exporting a schema derived via a transform',
      [
        "import * as z from 'zod';",
        "import { normalizeRepoUrl } from '@zyplux/util';",
        'export const RepoUrlSchema = z.string().transform(url => normalizeRepoUrl(url));',
      ].join('\n'),
    ],
    [
      '15.3.7 allows re-exporting an imported contracts schema by name',
      "export { IdSchema } from '@zyplux/util/contracts';",
    ],
    [
      '15.3.8 flags re-exporting a non-schema value from a relative module',
      "export { helper } from './helper';",
      'nonSchemaExport',
    ],
    ['15.3.9 flags re-exporting a non-schema value from zod', "export { z } from 'zod';", 'nonSchemaExport'],
    ['15.3.10 allows a type-only re-export', "export type { ZodType } from 'zod';"],
    ['15.3.11 flags a value star re-export from zod as unverifiable', "export * from 'zod';", 'nonSchemaExport'],
    [
      '15.3.12 flags a value star re-export from a contracts module as unverifiable',
      "export * from '@zyplux/util/contracts';",
      'nonSchemaExport',
    ],
    ['15.3.13 allows a type-only star re-export', "export type * from 'zod';"],
  ])('%s', runMaybeReportCase);
});

describe('15.4 freeing local statements while covering every export form', () => {
  test.for<MaybeReportCase>([
    [
      '15.4.1 allows non-schema locals, mutable bindings, and side-effecting statements',
      [
        "import * as z from 'zod';",
        "import { loadKinds } from './registry';",
        'const kinds = loadKinds();',
        'let lookups = 0;',
        'lookups += 1;',
        'console.log(kinds, lookups);',
        'export const IdSchema = z.string();',
      ].join('\n'),
    ],
    [
      '15.4.2 checks a default export of a schema against the schemas-only surface',
      "import * as z from 'zod';\nexport default z.string();",
    ],
    ['15.4.3 flags a default export of a non-schema value', 'export default { retries: 3 };', 'nonSchemaExport'],
    [
      '15.4.4 flags a mutable exported binding',
      "import * as z from 'zod';\nexport let MutableSchema = z.string();",
      'nonSchemaExport',
    ],
  ])('%s', runMaybeReportCase);
});

describe('15.5 scoping the rule to contracts files in the shipped config', () => {
  test('15.5.1 enables the rule only for src contracts files', ({ zyplux }) => {
    const config = zyplux();
    const contractEntries = config.filter(entry => entry.rules?.['@zyplux/contracts-only-schemas'] !== undefined);
    expect(contractEntries.map(entry => entry.files)).toEqual([['**/src/contracts.ts']]);
  });
});
