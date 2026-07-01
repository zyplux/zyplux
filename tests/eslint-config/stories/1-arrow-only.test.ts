import { Linter } from 'eslint';
import { describe, expect, it } from 'vitest';

import { getMergedRule } from '#merged-rule';

const arrowOnlyRule = await getMergedRule('no-restricted-syntax');

const linter = new Linter();

const arrowOnlyErrors = (code: string) => linter.verify(code, { rules: { 'no-restricted-syntax': arrowOnlyRule } });

const bannedSyntax = [{ ruleId: 'no-restricted-syntax' }];

describe('1.1 banning ordinary function declarations and expressions', () => {
  it('1.1.1 bans function declarations', () => {
    expect(arrowOnlyErrors('function foo() {}')).toMatchObject(bannedSyntax);
  });

  it('1.1.2 bans standalone function expressions', () => {
    expect(arrowOnlyErrors('const f = function () {};')).toMatchObject(bannedSyntax);
  });
});

describe('1.2 exempting generator functions, which have no arrow equivalent', () => {
  it('1.2.1 exempts generator function declarations', () => {
    expect(arrowOnlyErrors('function* gen() { yield 1; }')).toHaveLength(0);
  });

  it('1.2.2 exempts generator function expressions', () => {
    expect(arrowOnlyErrors('const stream = async function* () { yield 1; };')).toHaveLength(0);
  });
});

describe('1.3 exempting class and object methods, which have their own shorthand syntax', () => {
  it('1.3.1 exempts class methods', () => {
    expect(arrowOnlyErrors('class Foo { method() {} }')).toHaveLength(0);
  });

  it('1.3.2 exempts object literal shorthand methods', () => {
    expect(arrowOnlyErrors('const obj = { method() {} };')).toHaveLength(0);
  });
});
