import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-identity-cast' });

const identityCast = [{ messageId: 'noIdentityCast' }];

describe('6.1 flagging typed identity functions that act as disguised casts', () => {
  test('6.1.1 flags an expression-bodied identity with a typed parameter', ({ lintRule }) => {
    expect(lintRule('const asT = (x: number) => x;')).toMatchObject(identityCast);
  });

  test('6.1.2 flags an identity that also annotates the return position', ({ lintRule }) => {
    expect(lintRule('const asT = (x: Foo): Foo => x;')).toMatchObject(identityCast);
  });

  test('6.1.3 flags a block-bodied identity with a single return', ({ lintRule }) => {
    expect(lintRule('const asT = (x: number) => { return x; };')).toMatchObject(identityCast);
  });

  test('6.1.4 flags function declaration and object method identities', ({ lintRule }) => {
    expect(lintRule('function asNumber(x: number) { return x; }')).toMatchObject(identityCast);
    expect(lintRule('const o = { id(x: number) { return x; } };')).toMatchObject(identityCast);
  });
});

describe('6.2 permitting genuine pass-throughs and transforming bodies', () => {
  test('6.2.1 allows a generic identity, plain or constrained — the sanctioned pass-through', ({ lintRule }) => {
    expect(lintRule('const identity = <T>(x: T) => x;')).toHaveLength(0);
    expect(lintRule('const identity = <T extends object>(x: T) => x;')).toHaveLength(0);
  });

  test('6.2.2 allows an untyped parameter, which asserts no type', ({ lintRule }) => {
    expect(lintRule('const echo = (x) => x;')).toHaveLength(0);
  });

  test('6.2.3 allows a body that transforms the argument or returns a property', ({ lintRule }) => {
    expect(lintRule('const double = (x: number) => x * 2;')).toHaveLength(0);
    expect(lintRule('const first = (x: { a: number }) => x.a;')).toHaveLength(0);
  });

  test('6.2.4 allows more than one parameter and a block body that does more than return', ({ lintRule }) => {
    expect(lintRule('const keepFirst = (a: number, b: number) => a;')).toHaveLength(0);
    expect(lintRule('const relay = (x: number) => { log(x); return x; };')).toHaveLength(0);
  });
});
