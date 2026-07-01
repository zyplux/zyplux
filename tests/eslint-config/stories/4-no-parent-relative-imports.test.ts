import { Linter } from 'eslint';
import tseslint from 'typescript-eslint';
import { describe, expect, it } from 'vitest';

import { getMergedRule } from '#merged-rule';

const restrictedImportsRule = await getMergedRule('@typescript-eslint/no-restricted-imports');

const linter = new Linter();

const lint = (code: string) =>
  linter.verify(code, {
    languageOptions: { parser: tseslint.parser },
    plugins: { '@typescript-eslint': tseslint.plugin },
    rules: { '@typescript-eslint/no-restricted-imports': restrictedImportsRule },
  });

const parentImportViolation = [{ ruleId: '@typescript-eslint/no-restricted-imports' }];

describe('4. restricting parent-relative (../) imports', () => {
  describe('4.1 flagging parent-relative import specifiers', () => {
    it('4.1.1 flags a single level parent import', () => {
      expect(lint("import { x } from '../x';")).toMatchObject(parentImportViolation);
    });

    it('4.1.2 flags a deep parent import spanning multiple levels', () => {
      expect(lint("import { x } from '../../../x';")).toMatchObject(parentImportViolation);
    });

    it('4.1.3 flags a type only import from a parent path', () => {
      expect(lint("import type { X } from '../x';")).toMatchObject(parentImportViolation);
    });

    it('4.1.4 flags a re export from a parent path', () => {
      expect(lint("export { x } from '../x';")).toMatchObject(parentImportViolation);
    });
  });

  describe('4.2 permitting non-parent-relative import specifiers', () => {
    it('4.2.1 allows a same directory relative import', () => {
      expect(lint("import { x } from './x';")).toHaveLength(0);
    });

    it('4.2.2 allows a path alias import', () => {
      expect(lint("import { x } from '@/x';")).toHaveLength(0);
    });

    it('4.2.3 allows a bare package import', () => {
      expect(lint("import { x } from 'node:path';")).toHaveLength(0);
    });
  });

  describe('4.3 scoping the restriction to import declarations', () => {
    it('4.3.1 leaves a non import string argument untouched', () => {
      expect(lint("const p = path.resolve(dir, '../..');")).toHaveLength(0);
    });
  });
});
