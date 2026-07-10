import { describe, expect, test } from '#fixtures';

test.override({ ruleId: 'no-restricted-syntax' });

const bannedSyntax = [{ ruleId: 'no-restricted-syntax' }];

describe('1.1 banning ordinary function declarations and expressions', () => {
  test('1.1.1 bans function declarations', ({ lint }) => {
    expect(lint('function foo() {}')).toMatchObject(bannedSyntax);
  });

  test('1.1.2 bans standalone function expressions', ({ lint }) => {
    expect(lint('const f = function () {};')).toMatchObject(bannedSyntax);
  });
});

describe('1.2 exempting generator functions, which have no arrow equivalent', () => {
  test('1.2.1 exempts generator function declarations', ({ lint }) => {
    expect(lint('function* gen() { yield 1; }')).toReportNothing();
  });

  test('1.2.2 exempts generator function expressions', ({ lint }) => {
    expect(lint('const stream = async function* () { yield 1; };')).toReportNothing();
  });
});

describe('1.3 exempting class and object methods, which have their own shorthand syntax', () => {
  test('1.3.1 exempts class methods', ({ lint }) => {
    expect(lint('class Foo { method() {} }')).toReportNothing();
  });

  test('1.3.2 exempts object literal shorthand methods', ({ lint }) => {
    expect(lint('const obj = { method() {} };')).toReportNothing();
  });
});
