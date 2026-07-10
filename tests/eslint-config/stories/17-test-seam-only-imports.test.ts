import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'test-seam-only-imports' });

describe('17.1 allowing imports through the test seam', () => {
  test('17.1.1 allows fixture aliases and node builtins', ({ lintRule }) => {
    const code = ["import { describe } from '#fixtures';", "import path from 'node:path';"].join('\n');
    expect(lintRule(code)).toReportNothing();
  });

  test('17.1.2 allows third-party modules, value or type', ({ lintRule }) => {
    expect(lintRule("import * as z from 'zod';")).toReportNothing();
    expect(lintRule("import type { Linter } from 'eslint';")).toReportNothing();
  });
});

describe('17.2 flagging imports that reach around the seam', () => {
  test('17.2.1 flags file-path imports, including side-effect imports and re-exports', ({ lintRule }) => {
    expect(lintRule("import { helper } from './helper';")).toReport('pathImport');
    expect(lintRule("import '../src/setup';")).toReport('pathImport');
    expect(lintRule("export * from './helpers';")).toReport('pathImport');
  });

  test('17.2.2 flags bare specifiers that resolve to workspace source', ({ lintRule }) => {
    expect(lintRule("import { normalizeRepoUrl } from '@zyplux/util';")).toReport('workspaceImport');
    expect(lintRule("import { IdSchema } from '@zyplux/util/contracts';")).toReport('workspaceImport');
  });

  test('17.2.3 flags type-only and dynamic workspace imports', ({ lintRule }) => {
    expect(lintRule("import type { PackageJson } from '@zyplux/util/contracts';")).toReport('workspaceImport');
    expect(lintRule("export const load = () => import('@zyplux/util');")).toReport('workspaceImport');
  });
});

describe('17.3 scoping the rule to story tests in the shipped config', () => {
  test('17.3.1 enables the rule only for story test files', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/test-seam-only-imports'] !== undefined);
    expect(entries.map(entry => entry.files)).toEqual([['**/stories/*.test.{ts,tsx}']]);
  });
});
