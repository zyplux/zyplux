import { Linter } from 'eslint';
import { describe, expect, it } from 'vitest';

import { base } from '../src/configs/base';

const arrowOnlyRule = Array.isArray(base) ? undefined : base.rules?.['no-restricted-syntax'];

const linter = new Linter();

const arrowOnlyErrorCount = (code: string) =>
  linter.verify(code, { rules: { 'no-restricted-syntax': arrowOnlyRule ?? 'off' } }).length;

describe('arrow-only no-restricted-syntax', () => {
  it('still bans function declarations', () => {
    expect(arrowOnlyErrorCount('function foo() {}')).toBe(1);
  });

  it('still bans standalone function expressions', () => {
    expect(arrowOnlyErrorCount('const f = function () {};')).toBe(1);
  });

  it('exempts generator declarations — they have no arrow form', () => {
    expect(arrowOnlyErrorCount('function* gen() { yield 1; }')).toBe(0);
  });

  it('exempts async generator expressions', () => {
    expect(arrowOnlyErrorCount('const stream = async function* () { yield 1; };')).toBe(0);
  });
});
