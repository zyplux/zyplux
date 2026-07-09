import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'contracts-only-schemas' });

const contractsFile = { filename: 'src/contracts.ts' };

describe('15.1 accepting purely declarative contracts modules', () => {
  test('15.1.1 allows a module of zod imports and exported schema consts', ({ lintRule }) => {
    const code = [
      "import * as z from 'zod';",
      'export const UserSchema = z.object({ id: z.string() });',
      'export const OrderSchema = z.object({ user: UserSchema });',
    ].join('\n');
    expect(lintRule(code, contractsFile)).toHaveLength(0);
  });

  test('15.1.2 allows type-only exports and type-only zod imports', ({ lintRule }) => {
    const code = [
      "import type { ZodType } from 'zod';",
      "import * as z from 'zod';",
      'export const IdSchema = z.string();',
      'export type Id = z.infer<typeof IdSchema>;',
      'export type AnySchema = ZodType;',
    ].join('\n');
    expect(lintRule(code, contractsFile)).toHaveLength(0);
  });

  test('15.1.3 allows non-exported schema consts and schema-building helpers feeding exported schemas', ({
    lintRule,
  }) => {
    const code = [
      "import * as z from 'zod';",
      'const BaseSchema = z.object({ id: z.string() });',
      'const withTimestamps = (schema: typeof BaseSchema) => schema.extend({ createdAt: z.string() });',
      'export const RecordSchema = withTimestamps(BaseSchema);',
    ].join('\n');
    expect(lintRule(code, contractsFile)).toHaveLength(0);
  });
});

describe('15.2 rejecting non-schema exports', () => {
  test('15.2.1 flags an exported function', ({ lintRule }) => {
    const code = ["import * as z from 'zod';", 'export const parseId = (raw: string) => z.string().parse(raw);'].join(
      '\n',
    );
    expect(lintRule(code, contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
  });

  test('15.2.2 flags exported plain objects, function declarations, and classes', ({ lintRule }) => {
    expect(lintRule('export const config = { retries: 3 };', contractsFile)).toMatchObject([
      { messageId: 'nonSchemaExport' },
    ]);
    expect(lintRule('export function parse() {}', contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
    expect(lintRule('export class Contract {}', contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
  });

  test('15.2.3 flags a non-schema value in an export specifier list while allowing schemas and type specifiers', ({
    lintRule,
  }) => {
    const code = [
      "import * as z from 'zod';",
      'const UserSchema = z.object({ id: z.string() });',
      'const limit = 3;',
      'type User = z.infer<typeof UserSchema>;',
      'export { UserSchema, limit, type User };',
    ].join('\n');
    expect(lintRule(code, contractsFile)).toMatchObject([
      { messageId: 'nonSchemaConst' },
      { messageId: 'nonSchemaExport' },
    ]);
  });
});

describe('15.3 rejecting non-zod module edges', () => {
  test('15.3.1 flags imports from anything but zod, whether value, type, alias, or builtin', ({ lintRule }) => {
    expect(lintRule("import path from 'node:path';", contractsFile)).toMatchObject([{ messageId: 'nonZodImport' }]);
    expect(lintRule("import { helper } from './helper';", contractsFile)).toMatchObject([
      { messageId: 'nonZodImport' },
    ]);
    expect(lintRule("import type { Linter } from 'eslint';", contractsFile)).toMatchObject([
      { messageId: 'nonZodImport' },
    ]);
    expect(lintRule("import { schema } from '#contracts/base';", contractsFile)).toMatchObject([
      { messageId: 'nonZodImport' },
    ]);
  });

  test('15.3.2 flags re-exports from other modules', ({ lintRule }) => {
    expect(lintRule("export { OtherSchema } from './other';", contractsFile)).toMatchObject([
      { messageId: 'nonZodImport' },
    ]);
    expect(lintRule("export * from './other';", contractsFile)).toMatchObject([{ messageId: 'nonZodImport' }]);
  });

  test('15.3.3 flags value re-exports from zod while allowing type-only re-exports', ({ lintRule }) => {
    expect(lintRule("export { z } from 'zod';", contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
    expect(lintRule("export * from 'zod';", contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
    expect(lintRule("export type { ZodType } from 'zod';", contractsFile)).toHaveLength(0);
    expect(lintRule("export type * from 'zod';", contractsFile)).toHaveLength(0);
  });
});

describe('15.4 rejecting non-declarative statements', () => {
  test('15.4.1 flags non-schema local declarations and non-const bindings', ({ lintRule }) => {
    const code = ["import * as z from 'zod';", 'const limit = 3;', 'export const IdSchema = z.string();'].join('\n');
    expect(lintRule(code, contractsFile)).toMatchObject([{ messageId: 'nonSchemaConst' }]);
    expect(lintRule("import * as z from 'zod';\nlet MutableSchema = z.string();", contractsFile)).toMatchObject([
      { messageId: 'nonSchemaConst' },
    ]);
  });

  test('15.4.2 flags side-effecting statements and default exports', ({ lintRule }) => {
    expect(lintRule("import * as z from 'zod';\nconsole.log(z.string());", contractsFile)).toMatchObject([
      { messageId: 'forbiddenStatement' },
    ]);
    expect(lintRule("import * as z from 'zod';\nexport default z.string();", contractsFile)).toMatchObject([
      { messageId: 'forbiddenStatement' },
    ]);
  });
});

describe('15.5 scoping the rule to contracts files in the shipped config', () => {
  test('15.5.1 enables the rule only for src contracts files', ({ zyplux }) => {
    const config = zyplux();
    const contractEntries = config.filter(entry => entry.rules?.['@zyplux/contracts-only-schemas'] !== undefined);
    expect(contractEntries.map(entry => entry.files)).toEqual([['**/src/contracts.ts']]);
  });
});
