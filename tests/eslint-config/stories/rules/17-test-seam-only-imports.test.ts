import { describe, expect, test } from './rules.ts';

test.override({ ruleName: 'test-seam-only-imports' });

type Case = [shape: string, code: string];

describe('17.1 allowing the seam import', () => {
  test.for<Case>([
    [
      '1 allows describe, expect, and test from the fixtures alias',
      "import { describe, expect, test } from '#fixtures';",
    ],
    ['2 allows a variant test aliased to test', "import { describe, expect, test } from '#fixtures';"],
    ['3 allows a type-only import from the fixtures alias', "import type { ShellFake } from '#fixtures';"],
    [
      '4 allows a mixed type and value import from the fixtures alias',
      "import { test, type TempDir } from '#fixtures';",
    ],
  ])('17.1.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});

describe('17.2 flagging any module beyond the fixtures alias', () => {
  test.for<Case>([
    ['1 flags a node builtin', "import path from 'node:path';"],
    ['2 flags a third-party module', "import * as z from 'zod';"],
    ['3 flags a type-only import from a third-party module', "import type { Linter } from 'eslint';"],
    ['4 flags a workspace package import', "import { normalizeRepoUrl } from '@zyplux/util';"],
    ['5 flags a workspace package subpath import', "import { IdSchema } from '@zyplux/util/contracts';"],
    ['6 flags a side-effect import of a relative file path', "import '../src/setup';"],
    ['7 flags a re-export of a relative file path', "export * from './helpers';"],
    ['8 flags a dynamic import of a workspace package', "export const load = () => import('@zyplux/util');"],
  ])('17.2.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('moduleOutsideSeam');
  });
});

describe('17.3 flagging value bindings beyond describe, expect, and test', () => {
  test.for<Case>([
    ['1 flags another named value beyond the seam vocabulary', "import { storyMatchers } from '#fixtures';"],
    ['2 flags a helper renamed to test', "import { helper as test } from '#fixtures';"],
    ['3 flags a default import of the fixtures alias', "import fixtures from '#fixtures';"],
    ['4 flags a namespace import of the fixtures alias', "import * as fixtures from '#fixtures';"],
  ])('17.3.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('bindingOutsideSeam');
  });
});

describe('17.4 scoping the rule to tests in the shipped config', () => {
  test('17.4.1 enables the rule for test files inside and outside stories', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/test-seam-only-imports'] !== undefined);
    expect(entries.map(entry => entry.files)).toEqual([['**/*.test.{ts,tsx}']]);
  });
});

describe('17.5 using a local domain module', () => {
  test('17.5.1 allows the module named after the story directory', ({ lintRule }) => {
    expect(
      lintRule("import { describe, expect, test } from './api.ts';", {
        filename: 'stories/api/1-contract.test.ts',
      }),
    ).toReportNothing();
  });

  test('17.5.2 allows fixture types and aliases of actual API bindings', ({ lintRule }) => {
    expect(
      lintRule("import { type Api, describe as suite, test } from './api.ts';", {
        filename: 'stories/api/1-contract.test.ts',
      }),
    ).toReportNothing();
  });

  test('17.5.3 flags a helper imported directly into a domain story', ({ lintRule }) => {
    expect(
      lintRule("import { runScenario } from './helpers.ts';", { filename: 'stories/api/1-contract.test.ts' }),
    ).toReport('moduleOutsideSeam');
  });

  test('17.5.4 flags extra value bindings from a domain module', ({ lintRule }) => {
    expect(
      lintRule("import { runScenario } from './api.ts';", { filename: 'stories/api/1-contract.test.ts' }),
    ).toReport('bindingOutsideSeam');
  });

  test('17.5.5 flags a module named after a parent domain', ({ lintRule }) => {
    expect(lintRule("import { test } from './api.ts';", { filename: 'stories/api/admin/1-contract.test.ts' })).toReport(
      'moduleOutsideSeam',
    );
  });

  test('17.5.6 flags dynamic imports of a domain helper', ({ lintRule }) => {
    expect(
      lintRule("export const load = () => import('./helpers.ts');", {
        filename: 'stories/api/1-contract.test.ts',
      }),
    ).toReport('moduleOutsideSeam');
  });
});
