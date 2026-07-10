import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-identity-cast' });

describe('6.1 flagging typed identity functions that act as disguised casts', () => {
  test('6.1.1 flags an expression-bodied identity with a typed parameter', ({ lintRule }) => {
    expect(lintRule('const asT = (x: number) => x;')).toReport('noIdentityCast');
  });

  test('6.1.2 flags an identity that also annotates the return position', ({ lintRule }) => {
    expect(lintRule('const asT = (x: Foo): Foo => x;')).toReport('noIdentityCast');
  });

  test('6.1.3 flags a block-bodied identity with a single return', ({ lintRule }) => {
    expect(lintRule('const asT = (x: number) => { return x; };')).toReport('noIdentityCast');
  });

  test('6.1.4 flags function declaration and object method identities', ({ lintRule }) => {
    expect(lintRule('function asNumber(x: number) { return x; }')).toReport('noIdentityCast');
    expect(lintRule('const o = { id(x: number) { return x; } };')).toReport('noIdentityCast');
  });
});

describe('6.2 permitting genuine pass-throughs and transforming bodies', () => {
  test('6.2.1 allows a generic identity, plain or constrained — the sanctioned pass-through', ({ lintRule }) => {
    expect(lintRule('const identity = <T>(x: T) => x;')).toReportNothing();
    expect(lintRule('const identity = <T extends object>(x: T) => x;')).toReportNothing();
  });

  test('6.2.2 allows an untyped parameter, which asserts no type', ({ lintRule }) => {
    expect(lintRule('const echo = (x) => x;')).toReportNothing();
  });

  test('6.2.3 allows a body that transforms the argument or returns a property', ({ lintRule }) => {
    expect(lintRule('const double = (x: number) => x * 2;')).toReportNothing();
    expect(lintRule('const first = (x: { a: number }) => x.a;')).toReportNothing();
  });

  test('6.2.4 allows more than one parameter and a block body that does more than return', ({ lintRule }) => {
    expect(lintRule('const keepFirst = (a: number, b: number) => a;')).toReportNothing();
    expect(lintRule('const relay = (x: number) => { log(x); return x; };')).toReportNothing();
  });
});
