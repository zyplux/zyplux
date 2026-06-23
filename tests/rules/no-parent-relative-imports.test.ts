import { Linter } from 'eslint';
import tseslint from 'typescript-eslint';
import { describe, expect, it } from 'vitest';

import { getMergedRule } from './merged-rule';

const restrictedImportsRule = await getMergedRule('@typescript-eslint/no-restricted-imports');

const linter = new Linter();

const restrictedImportErrors = (code: string) =>
  linter.verify(code, {
    languageOptions: { parser: tseslint.parser },
    plugins: { '@typescript-eslint': tseslint.plugin },
    rules: { '@typescript-eslint/no-restricted-imports': restrictedImportsRule },
  });

const parentImport = [{ ruleId: '@typescript-eslint/no-restricted-imports' }];

describe('no parent-relative (../) imports', () => {
  it('flags a single-level parent import', () => {
    expect(restrictedImportErrors("import { x } from '../x';")).toMatchObject(parentImport);
  });

  it('flags a deep parent import — regex matches every depth, unlike a glob', () => {
    expect(restrictedImportErrors("import { x } from '../../../x';")).toMatchObject(parentImport);
  });

  it('flags `import type` — the TS-aware variant inspects type-only imports', () => {
    expect(restrictedImportErrors("import type { X } from '../x';")).toMatchObject(parentImport);
  });

  it('flags `export … from` re-exports', () => {
    expect(restrictedImportErrors("export { x } from '../x';")).toMatchObject(parentImport);
  });

  it('allows same-directory relative imports', () => {
    expect(restrictedImportErrors("import { x } from './x';")).toHaveLength(0);
  });

  it('allows path-alias imports', () => {
    expect(restrictedImportErrors("import { x } from '@/x';")).toHaveLength(0);
  });

  it('allows bare package imports', () => {
    expect(restrictedImportErrors("import { x } from 'node:path';")).toHaveLength(0);
  });

  it('leaves non-import string arguments untouched', () => {
    expect(restrictedImportErrors("const p = path.resolve(dir, '../..');")).toHaveLength(0);
  });
});
