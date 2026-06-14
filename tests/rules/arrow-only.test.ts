import { zyplux } from '@zyplux/eslint-config';
import { describe, expect, it } from 'bun:test';
import { Linter } from 'eslint';

const config = zyplux();
const arrowOnlyEntry = config.find(entry => entry.rules?.['no-restricted-syntax'] !== undefined);
const arrowOnlyRule = arrowOnlyEntry?.rules?.['no-restricted-syntax'] ?? 'off';

const linter = new Linter();

const arrowOnlyErrorCount = (code: string) =>
  linter.verify(code, { rules: { 'no-restricted-syntax': arrowOnlyRule } }).length;

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
