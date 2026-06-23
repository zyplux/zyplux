import { Linter } from 'eslint';
import { describe, expect, it } from 'vitest';

import { getMergedRule } from './merged-rule';

const arrowOnlyRule = await getMergedRule('no-restricted-syntax');

const linter = new Linter();

const arrowOnlyErrors = (code: string) => linter.verify(code, { rules: { 'no-restricted-syntax': arrowOnlyRule } });

const bannedSyntax = [{ ruleId: 'no-restricted-syntax' }];

describe('arrow-only no-restricted-syntax', () => {
  it('still bans function declarations', () => {
    expect(arrowOnlyErrors('function foo() {}')).toMatchObject(bannedSyntax);
  });

  it('still bans standalone function expressions', () => {
    expect(arrowOnlyErrors('const f = function () {};')).toMatchObject(bannedSyntax);
  });

  it('exempts generator declarations — they have no arrow form', () => {
    expect(arrowOnlyErrors('function* gen() { yield 1; }')).toHaveLength(0);
  });

  it('exempts async generator expressions', () => {
    expect(arrowOnlyErrors('const stream = async function* () { yield 1; };')).toHaveLength(0);
  });
});
