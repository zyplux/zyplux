import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-schemas-outside-contracts' });

describe('16.1 keeping schema construction in contracts', () => {
  test('16.1.1 flags a zod value import and the schema const it builds', ({ lintRule }) => {
    const code = ["import * as z from 'zod';", 'const UserSchema = z.object({ id: z.string() });'].join('\n');
    expect(lintRule(code)).toMatchObject([{ messageId: 'zodValueImport' }, { messageId: 'schemaDeclaration' }]);
  });

  test('16.1.2 flags a schema composed inline from an imported contracts schema', ({ lintRule }) => {
    const code = [
      "import { PackageJsonSchema } from '@zyplux/util/contracts';",
      'export const readManifests = (raw: unknown) => PackageJsonSchema.array().parse(raw);',
    ].join('\n');
    expect(lintRule(code)).toMatchObject([{ messageId: 'schemaConstruction' }]);
  });

  test('16.1.3 reports a construction chain once at its declaration', ({ lintRule }) => {
    const code = ["import * as z from 'zod';", 'const TagsSchema = z.array(z.string()).optional();'].join('\n');
    expect(lintRule(code)).toMatchObject([{ messageId: 'zodValueImport' }, { messageId: 'schemaDeclaration' }]);
  });
});

describe('16.2 allowing schema use outside contracts', () => {
  test('16.2.1 allows importing a contracts schema and parsing with it', ({ lintRule }) => {
    const code = [
      "import { PackageJsonSchema } from '@zyplux/util/contracts';",
      'export const readManifest = (raw: string) => PackageJsonSchema.parse(JSON.parse(raw));',
    ].join('\n');
    expect(lintRule(code)).toHaveLength(0);
  });

  test('16.2.2 allows type-only zod imports, schema-typed parameters, and inferred types', ({ lintRule }) => {
    const code = [
      "import type { ZodType } from 'zod';",
      'export const parseWith = <Parsed>(schema: ZodType<Parsed>, raw: unknown) => schema.parse(raw);',
    ].join('\n');
    expect(lintRule(code)).toHaveLength(0);
    expect(lintRule("import { type ZodType } from 'zod';")).toHaveLength(0);
    const inferred = [
      "import type * as z from 'zod';",
      "import { PackageJsonSchema } from '@zyplux/util/contracts';",
      'export type Manifest = z.infer<typeof PackageJsonSchema>;',
    ].join('\n');
    expect(lintRule(inferred)).toHaveLength(0);
  });
});

describe('16.3 scoping the rule to source files in the shipped config', () => {
  test('16.3.1 enables the rule for source files while exempting the contracts module', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/no-schemas-outside-contracts'] !== undefined);
    expect(entries.map(entry => [entry.files, entry.ignores])).toEqual([
      [['**/src/**/*.{ts,tsx}'], ['**/src/contracts.ts']],
    ]);
  });
});
