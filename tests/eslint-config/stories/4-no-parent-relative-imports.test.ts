import { describe, expect, test } from '#fixtures';

test.override({ ruleId: '@typescript-eslint/no-restricted-imports' });

const parentImportViolation = [{ ruleId: '@typescript-eslint/no-restricted-imports' }];

describe('4. restricting parent-relative (../) imports', () => {
  describe('4.1 flagging parent-relative import specifiers', () => {
    test('4.1.1 flags a parent import at any depth', ({ lint }) => {
      expect(lint("import { x } from '../x';")).toMatchObject(parentImportViolation);
      expect(lint("import { x } from '../../../x';")).toMatchObject(parentImportViolation);
    });

    test('4.1.2 flags a type only import from a parent path', ({ lint }) => {
      expect(lint("import type { X } from '../x';")).toMatchObject(parentImportViolation);
    });

    test('4.1.3 flags a re export from a parent path', ({ lint }) => {
      expect(lint("export { x } from '../x';")).toMatchObject(parentImportViolation);
    });
  });

  describe('4.2 permitting non-parent-relative import specifiers', () => {
    test('4.2.1 allows a same directory relative import', ({ lint }) => {
      expect(lint("import { x } from './x';")).toReportNothing();
    });

    test('4.2.2 allows alias and bare package imports', ({ lint }) => {
      expect(lint("import { x } from '@/x';")).toReportNothing();
      expect(lint("import { x } from 'node:path';")).toReportNothing();
    });
  });
});
