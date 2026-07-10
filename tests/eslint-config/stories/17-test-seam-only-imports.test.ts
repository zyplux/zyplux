import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'test-seam-only-imports' });

describe('17.1 allowing the seam import', () => {
  test('17.1.1 allows describe, expect, and test from the fixtures alias, including a variant test aliased to test', ({
    lintRule,
  }) => {
    expect(lintRule("import { describe, expect, test } from '#fixtures';")).toReportNothing();
    expect(lintRule("import { describe, expect, targetsTest as test } from '#fixtures';")).toReportNothing();
  });

  test('17.1.2 allows type-only imports from the fixtures alias', ({ lintRule }) => {
    expect(lintRule("import type { ShellFake } from '#fixtures';")).toReportNothing();
    expect(lintRule("import { test, type TempDir } from '#fixtures';")).toReportNothing();
  });
});

describe('17.2 flagging any module beyond the fixtures alias', () => {
  test('17.2.1 flags node builtins and third-party modules', ({ lintRule }) => {
    expect(lintRule("import path from 'node:path';")).toReport('moduleOutsideSeam');
    expect(lintRule("import * as z from 'zod';")).toReport('moduleOutsideSeam');
    expect(lintRule("import type { Linter } from 'eslint';")).toReport('moduleOutsideSeam');
  });

  test('17.2.2 flags workspace packages and file paths, including side-effect imports and re-exports', ({
    lintRule,
  }) => {
    expect(lintRule("import { normalizeRepoUrl } from '@zyplux/util';")).toReport('moduleOutsideSeam');
    expect(lintRule("import { IdSchema } from '@zyplux/util/contracts';")).toReport('moduleOutsideSeam');
    expect(lintRule("import '../src/setup';")).toReport('moduleOutsideSeam');
    expect(lintRule("export * from './helpers';")).toReport('moduleOutsideSeam');
  });

  test('17.2.3 flags dynamic imports of any module beyond the fixtures alias', ({ lintRule }) => {
    expect(lintRule("export const load = () => import('@zyplux/util');")).toReport('moduleOutsideSeam');
  });
});

describe('17.3 flagging value bindings beyond describe, expect, and test', () => {
  test('17.3.1 flags other named values and renames away from the seam vocabulary', ({ lintRule }) => {
    expect(lintRule("import { storyMatchers } from '#fixtures';")).toReport('bindingOutsideSeam');
    expect(lintRule("import { describe as suite } from '#fixtures';")).toReport('bindingOutsideSeam');
  });

  test('17.3.2 flags default and namespace imports of the fixtures alias', ({ lintRule }) => {
    expect(lintRule("import fixtures from '#fixtures';")).toReport('bindingOutsideSeam');
    expect(lintRule("import * as fixtures from '#fixtures';")).toReport('bindingOutsideSeam');
  });
});

describe('17.4 scoping the rule to story tests in the shipped config', () => {
  test('17.4.1 enables the rule only for story test files', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/test-seam-only-imports'] !== undefined);
    expect(entries.map(entry => entry.files)).toEqual([['**/stories/*.test.{ts,tsx}']]);
  });
});
