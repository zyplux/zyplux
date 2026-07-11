import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-schemas-outside-contracts' });

type ReportCase = [shape: string, code: string, ids: ReportIds];
type ReportIds = readonly [string, ...string[]];
type ReportNothingCase = [shape: string, code: string];

describe('16.1 keeping schema construction in contracts', () => {
  test.for<ReportCase>([
    [
      '16.1.1 flags a zod value import and the schema const it builds',
      ["import * as z from 'zod';", 'const UserSchema = z.object({ id: z.string() });'].join('\n'),
      ['zodValueImport', 'schemaDeclaration'],
    ],
    [
      '16.1.2 flags a schema composed inline from an imported contracts schema',
      [
        "import { PackageJsonSchema } from '@zyplux/util/contracts';",
        'export const readManifests = (raw: unknown) => PackageJsonSchema.array().parse(raw);',
      ].join('\n'),
      ['schemaConstruction'],
    ],
    [
      '16.1.3 reports a construction chain once at its declaration',
      ["import * as z from 'zod';", 'const TagsSchema = z.array(z.string()).optional();'].join('\n'),
      ['zodValueImport', 'schemaDeclaration'],
    ],
    ['16.1.4 flags a named value import that exposes a schema factory', "import { z } from 'zod';", ['zodValueImport']],
    [
      '16.1.5 flags a named object import that exposes a schema factory',
      "import { object } from 'zod';",
      ['zodValueImport'],
    ],
  ])('%s', ([, code, ids], { lintRule }) => {
    expect(lintRule(code)).toReport(...ids);
  });
});

describe('16.2 allowing schema use outside contracts', () => {
  test.for<ReportNothingCase>([
    [
      '16.2.1 allows importing a contracts schema and parsing with it',
      [
        "import { PackageJsonSchema } from '@zyplux/util/contracts';",
        'export const readManifest = (raw: string) => PackageJsonSchema.parse(JSON.parse(raw));',
      ].join('\n'),
    ],
    [
      '16.2.2 allows a schema-typed parameter and type-only zod import',
      [
        "import type { ZodType } from 'zod';",
        'export const parseWith = <Parsed>(schema: ZodType<Parsed>, raw: unknown) => schema.parse(raw);',
      ].join('\n'),
    ],
    ['16.2.3 allows a type-only import combined with a value import', "import { type ZodType } from 'zod';"],
    [
      '16.2.4 allows an inferred type from an imported contracts schema',
      [
        "import type * as z from 'zod';",
        "import { PackageJsonSchema } from '@zyplux/util/contracts';",
        'export type Manifest = z.infer<typeof PackageJsonSchema>;',
      ].join('\n'),
    ],
    [
      '16.2.5 allows named zod values that cannot build schemas',
      [
        "import { ZodError } from 'zod';",
        'export const describeSchemaError = (error: unknown) => (error instanceof ZodError ? error.message : undefined);',
      ].join('\n'),
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});

describe('16.3 scoping the rule to every typescript file in the shipped config', () => {
  test('16.3.1 enables the rule for every typescript file while exempting the contracts modules', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/no-schemas-outside-contracts'] !== undefined);
    expect(entries.map(entry => [entry.files, entry.ignores])).toEqual([[['**/*.{ts,tsx}'], ['**/src/contracts.ts']]]);
  });
});
