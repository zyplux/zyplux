import { describe, expect, test } from '#fixtures';

test.override({ ruleId: 'no-restricted-syntax' });

const bannedSyntax = [{ ruleId: 'no-restricted-syntax' }];

type ArrowCase = [shape: string, code: string];

describe('1.1 banning ordinary function declarations and expressions', () => {
  const cases: ArrowCase[] = [
    ['1 bans function declarations', 'function foo() {}'],
    ['2 bans standalone function expressions', 'const f = function () {};'],
  ];

  test.for(cases)('1.1.%s', ([, code], { lint }) => {
    expect(lint(code)).toMatchObject(bannedSyntax);
  });
});

describe('1.2 exempting syntax with no arrow equivalent or its own shorthand', () => {
  const cases: ArrowCase[] = [
    ['1 exempts generator function declarations', 'function* gen() { yield 1; }'],
    ['2 exempts generator function expressions', 'const stream = async function* () { yield 1; };'],
    ['3 exempts class methods', 'class Foo { method() {} }'],
    ['4 exempts object literal shorthand methods', 'const obj = { method() {} };'],
  ];

  test.for(cases)('1.2.%s', ([, code], { lint }) => {
    expect(lint(code)).toReportNothing();
  });
});
