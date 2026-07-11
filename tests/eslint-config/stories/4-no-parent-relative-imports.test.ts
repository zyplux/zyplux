import { describe, expect, test } from '#fixtures';

test.override({ ruleId: '@typescript-eslint/no-restricted-imports' });

const parentImportViolation = [{ ruleId: '@typescript-eslint/no-restricted-imports' }];

type ImportCase = [shape: string, codes: string[]];

describe('4. restricting parent-relative (../) imports', () => {
  describe('4.1 flagging parent-relative import specifiers', () => {
    const cases: ImportCase[] = [
      ['4.1.1 flags a parent import at any depth', ["import { x } from '../x';", "import { x } from '../../../x';"]],
      ['4.1.2 flags a type only import from a parent path', ["import type { X } from '../x';"]],
      ['4.1.3 flags a re export from a parent path', ["export { x } from '../x';"]],
    ];

    test.for(cases)('%s', ([, codes], { lint }) => {
      for (const code of codes) expect(lint(code)).toMatchObject(parentImportViolation);
    });
  });

  describe('4.2 permitting non-parent-relative import specifiers', () => {
    const cases: ImportCase[] = [
      ['4.2.1 allows a same directory relative import', ["import { x } from './x';"]],
      ['4.2.2 allows alias and bare package imports', ["import { x } from '@/x';", "import { x } from 'node:path';"]],
    ];

    test.for(cases)('%s', ([, codes], { lint }) => {
      for (const code of codes) expect(lint(code)).toReportNothing();
    });
  });
});
