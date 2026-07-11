import { describe, test } from '#fixtures';

test.override({ ruleName: 'no-type-predicate' });

type TypePredicateCase = [shape: string, codes: string[]];

describe('7.1 flagging user-defined type guards in every function form', () => {
  const cases: TypePredicateCase[] = [
    [
      '7.1.1 flags arrow, declaration, and expression type guards',
      [
        'const isString = (x: unknown): x is string => typeof x === "string";',
        'function isString(x: unknown): x is string { return typeof x === "string"; }',
        'const isString = function (x: unknown): x is string { return typeof x === "string"; };',
      ],
    ],
    [
      '7.1.2 flags class method and interface method signature type guards',
      [
        'class A { isString(x: unknown): x is string { return typeof x === "string"; } }',
        'interface I { isString(x: unknown): x is string; }',
      ],
    ],
    [
      '7.1.3 flags function type alias and ambient declaration type guards',
      ['type Guard = (x: unknown) => x is string;', 'declare function isString(x: unknown): x is string;'],
    ],
    [
      '7.1.4 flags a this-based type guard',
      ['const isThis = function (this: unknown): this is string { return typeof this === "string"; };'],
    ],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReport, lintRule }) => {
    expectEachToReport(lintRule, codes, 'noTypePredicate');
  });
});

describe('7.2 permitting predicate-free checks and assertion signatures', () => {
  const cases: TypePredicateCase[] = [
    [
      '7.2.1 allows a boolean check without a predicate annotation',
      [
        'const isString = (x: unknown) => typeof x === "string";',
        'function isString(x: unknown) { return typeof x === "string"; }',
      ],
    ],
    [
      '7.2.2 allows assertion signatures, with or without a predicate',
      [
        'function assert(cond: unknown): asserts cond {}',
        'function assertString(x: unknown): asserts x is string { if (typeof x !== "string") throw new Error(); }',
      ],
    ],
    ['7.2.3 allows a regular typed function with no predicate', ['const greet = (): string => "hi";']],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});
