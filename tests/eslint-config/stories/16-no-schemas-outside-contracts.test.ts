import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-schemas-outside-contracts' });

type ReportCase = [shape: string, code: string];
type ReportNothingCase = [shape: string, code: string];

describe('16.1 keeping schema exports in contracts', () => {
  test.for<ReportCase>([
    [
      '1 flags an exported schema declaration',
      "import * as z from 'zod';\nexport const UserSchema = z.object({ id: z.string() });",
    ],
    [
      '2 flags a schema exported after its declaration',
      "import * as z from 'zod';\nconst UserSchema = z.object({ id: z.string() });\nexport { UserSchema };",
    ],
    [
      '3 flags a default schema export',
      "import * as z from 'zod';\nconst UserSchema = z.object({ id: z.string() });\nexport default UserSchema;",
    ],
  ])('16.1.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('schemaExport');
  });
});

describe('16.2 allowing local schema implementation', () => {
  test.for<ReportNothingCase>([
    [
      '1 allows zod imports and local schema construction',
      "import * as z from 'zod';\nconst UserSchema = z.object({ id: z.string() });\nexport const readUser = (raw: unknown) => UserSchema.parse(raw);",
    ],
    [
      '2 allows composing an imported schema locally',
      "import { PackageJsonSchema } from '@zyplux/util/contracts';\nconst PackageListSchema = PackageJsonSchema.array();\nexport const readManifests = (raw: unknown) => PackageListSchema.parse(raw);",
    ],
    [
      '3 allows a schema-typed parameter and type-only zod import',
      "import { type ZodType } from 'zod';\nexport { type ZodType };\nexport const parseWith = <Parsed>(schema: ZodType<Parsed>, raw: unknown) => schema.parse(raw);",
    ],
    [
      '4 allows an inferred type from an imported contracts schema',
      "import type * as z from 'zod';\nimport { PackageJsonSchema } from '@zyplux/util/contracts';\nexport type Manifest = z.infer<typeof PackageJsonSchema>;",
    ],
    ['5 allows non-schema declaration exports', 'export function getName() { return "zyplux"; }'],
  ])('16.2.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});

describe('16.3 scoping the rule to implementation files', () => {
  test('16.3.1 enables the rule while exempting contracts entrypoints and child modules', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/no-schemas-outside-contracts'] !== undefined);
    expect(entries.map(entry => [entry.files, entry.ignores])).toEqual([
      [['**/*.{ts,tsx}'], ['**/src/contracts.ts', '**/src/contracts/**/*.ts']],
    ]);
  });
});

describe('16.4 keeping schema collections in contracts', () => {
  test.for([
    'export const Schema = { text: z.string() };',
    'export default { nested: { text: z.string() } };',
    'const Schema = { text: z.string() }; export { Schema };',
    'export { GhSchema } from "@zyplux/util/contracts";',
  ])('16.4.1 rejects schema collection exports: %s', (code, { lintRule }) => {
    expect(lintRule(`import * as z from "zod"; ${code}`)).toReport('schemaExport');
  });

  test('16.4.2 permits ordinary configuration objects', ({ lintRule }) => {
    expect(
      lintRule('import * as z from "zod"; export const config = { text: z.string(), retries: 3 };'),
    ).toReportNothing();
  });
});
