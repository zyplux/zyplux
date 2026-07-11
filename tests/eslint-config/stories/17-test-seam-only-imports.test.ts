import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'test-seam-only-imports' });

type Case = [shape: string, code: string];

describe('17.1 allowing the seam import', () => {
  test.for<Case>([
    [
      '17.1.1 allows describe, expect, and test from the fixtures alias',
      "import { describe, expect, test } from '#fixtures';",
    ],
    [
      '17.1.2 allows a variant test aliased to test',
      "import { describe, expect, targetsTest as test } from '#fixtures';",
    ],
    ['17.1.3 allows a type-only import from the fixtures alias', "import type { ShellFake } from '#fixtures';"],
    [
      '17.1.4 allows a mixed type and value import from the fixtures alias',
      "import { test, type TempDir } from '#fixtures';",
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});

describe('17.2 flagging any module beyond the fixtures alias', () => {
  test.for<Case>([
    ['17.2.1 flags a node builtin', "import path from 'node:path';"],
    ['17.2.2 flags a third-party module', "import * as z from 'zod';"],
    ['17.2.3 flags a type-only import from a third-party module', "import type { Linter } from 'eslint';"],
    ['17.2.4 flags a workspace package import', "import { normalizeRepoUrl } from '@zyplux/util';"],
    ['17.2.5 flags a workspace package subpath import', "import { IdSchema } from '@zyplux/util/contracts';"],
    ['17.2.6 flags a side-effect import of a relative file path', "import '../src/setup';"],
    ['17.2.7 flags a re-export of a relative file path', "export * from './helpers';"],
    ['17.2.8 flags a dynamic import of a workspace package', "export const load = () => import('@zyplux/util');"],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('moduleOutsideSeam');
  });
});

describe('17.3 flagging value bindings beyond describe, expect, and test', () => {
  test.for<Case>([
    ['17.3.1 flags another named value beyond the seam vocabulary', "import { storyMatchers } from '#fixtures';"],
    ['17.3.2 flags a rename away from the seam vocabulary', "import { describe as suite } from '#fixtures';"],
    ['17.3.3 flags a default import of the fixtures alias', "import fixtures from '#fixtures';"],
    ['17.3.4 flags a namespace import of the fixtures alias', "import * as fixtures from '#fixtures';"],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('bindingOutsideSeam');
  });
});

describe('17.4 scoping the rule to story tests in the shipped config', () => {
  test('17.4.1 enables the rule only for story test files', ({ zyplux }) => {
    const config = zyplux();
    const entries = config.filter(entry => entry.rules?.['@zyplux/test-seam-only-imports'] !== undefined);
    expect(entries.map(entry => entry.files)).toEqual([['**/stories/*.test.{ts,tsx}']]);
  });
});
