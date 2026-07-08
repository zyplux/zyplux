import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-type-predicate' });

const typePredicate = [{ messageId: 'noTypePredicate' }];

describe('7.1 flagging user-defined type guards in every function form', () => {
  test('7.1.1 flags arrow, declaration, and expression type guards', ({ lintRule }) => {
    expect(lintRule('const isString = (x: unknown): x is string => typeof x === "string";')).toMatchObject(
      typePredicate,
    );
    expect(lintRule('function isString(x: unknown): x is string { return typeof x === "string"; }')).toMatchObject(
      typePredicate,
    );
    expect(
      lintRule('const isString = function (x: unknown): x is string { return typeof x === "string"; };'),
    ).toMatchObject(typePredicate);
  });

  test('7.1.2 flags class method and interface method signature type guards', ({ lintRule }) => {
    expect(lintRule('class A { isString(x: unknown): x is string { return typeof x === "string"; } }')).toMatchObject(
      typePredicate,
    );
    expect(lintRule('interface I { isString(x: unknown): x is string; }')).toMatchObject(typePredicate);
  });

  test('7.1.3 flags function type alias and ambient declaration type guards', ({ lintRule }) => {
    expect(lintRule('type Guard = (x: unknown) => x is string;')).toMatchObject(typePredicate);
    expect(lintRule('declare function isString(x: unknown): x is string;')).toMatchObject(typePredicate);
  });

  test('7.1.4 flags a this-based type guard', ({ lintRule }) => {
    expect(
      lintRule('const isThis = function (this: unknown): this is string { return typeof this === "string"; };'),
    ).toMatchObject(typePredicate);
  });
});

describe('7.2 permitting predicate-free checks and assertion signatures', () => {
  test('7.2.1 allows a boolean check without a predicate annotation', ({ lintRule }) => {
    expect(lintRule('const isString = (x: unknown) => typeof x === "string";')).toHaveLength(0);
    expect(lintRule('function isString(x: unknown) { return typeof x === "string"; }')).toHaveLength(0);
  });

  test('7.2.2 allows assertion signatures, with or without a predicate', ({ lintRule }) => {
    expect(lintRule('function assert(cond: unknown): asserts cond {}')).toHaveLength(0);
    expect(
      lintRule(
        'function assertString(x: unknown): asserts x is string { if (typeof x !== "string") throw new Error(); }',
      ),
    ).toHaveLength(0);
  });

  test('7.2.3 allows a regular typed function with no predicate', ({ lintRule }) => {
    expect(lintRule('const greet = (): string => "hi";')).toHaveLength(0);
  });
});
