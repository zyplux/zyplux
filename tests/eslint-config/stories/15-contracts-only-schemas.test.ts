import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'contracts-only-schemas' });

const contractsFile = { filename: 'src/contracts.ts' };

describe('15.1 accepting schemas-only export surfaces', () => {
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
    expect(lintRule(code, contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
  });
});

describe('15.3 opening imports while holding the export surface', () => {
  test('15.3.1 allows imports from any module, value or type', ({ lintRule }) => {
    expect(lintRule("import path from 'node:path';", contractsFile)).toHaveLength(0);
    expect(lintRule("import { helper } from './helper';", contractsFile)).toHaveLength(0);
    expect(lintRule("import type { Linter } from 'eslint';", contractsFile)).toHaveLength(0);
    expect(lintRule("import { schema } from '#contracts/base';", contractsFile)).toHaveLength(0);
  });

  test('15.3.2 allows building and re-exporting schemas from any source', ({ lintRule }) => {
    const composed = [
      "import * as z from 'zod';",
      "import { IdSchema } from '@zyplux/util/contracts';",
      'export const ProjectKeySchema = z.object({ projectKey: IdSchema });',
    ].join('\n');
    expect(lintRule(composed, contractsFile)).toHaveLength(0);
    const derived = [
      "import * as z from 'zod';",
      "import { normalizeRepoUrl } from '@zyplux/util';",
      'export const RepoUrlSchema = z.string().transform(url => normalizeRepoUrl(url));',
    ].join('\n');
    expect(lintRule(derived, contractsFile)).toHaveLength(0);
    expect(lintRule("export { IdSchema } from '@zyplux/util/contracts';", contractsFile)).toHaveLength(0);
  });

  test('15.3.3 flags re-exporting non-schema values while allowing type-only re-exports', ({ lintRule }) => {
    expect(lintRule("export { helper } from './helper';", contractsFile)).toMatchObject([
      { messageId: 'nonSchemaExport' },
    ]);
    expect(lintRule("export { z } from 'zod';", contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
    expect(lintRule("export type { ZodType } from 'zod';", contractsFile)).toHaveLength(0);
  });

  test('15.3.4 flags value star re-exports as unverifiable while allowing type-only star re-exports', ({
    lintRule,
  }) => {
    expect(lintRule("export * from 'zod';", contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
    expect(lintRule("export * from '@zyplux/util/contracts';", contractsFile)).toMatchObject([
      { messageId: 'nonSchemaExport' },
    ]);
    expect(lintRule("export type * from 'zod';", contractsFile)).toHaveLength(0);
  });
});

describe('15.4 freeing local statements while covering every export form', () => {
  test('15.4.1 allows non-schema locals, mutable bindings, and side-effecting statements', ({ lintRule }) => {
    const code = [
      "import * as z from 'zod';",
      "import { loadKinds } from './registry';",
      'const kinds = loadKinds();',
      'let lookups = 0;',
      'lookups += 1;',
      'console.log(kinds, lookups);',
      'export const IdSchema = z.string();',
    ].join('\n');
    expect(lintRule(code, contractsFile)).toHaveLength(0);
  });

  test('15.4.2 checks a default export against the schemas-only surface', ({ lintRule }) => {
    expect(lintRule("import * as z from 'zod';\nexport default z.string();", contractsFile)).toHaveLength(0);
    expect(lintRule('export default { retries: 3 };', contractsFile)).toMatchObject([{ messageId: 'nonSchemaExport' }]);
  });

  test('15.4.3 flags a mutable exported binding', ({ lintRule }) => {
    expect(lintRule("import * as z from 'zod';\nexport let MutableSchema = z.string();", contractsFile)).toMatchObject([
      { messageId: 'nonSchemaExport' },
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
