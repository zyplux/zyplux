import { describe, test } from '#fixtures';

test.override({ ruleName: 'no-identity-cast' });

type IdentityCastCase = [shape: string, codes: string[]];

describe('6.1 flagging typed identity functions that act as disguised casts', () => {
  const cases: IdentityCastCase[] = [
    ['1 flags an expression-bodied identity with a typed parameter', ['const asT = (x: number) => x;']],
    ['2 flags an identity that also annotates the return position', ['const asT = (x: Foo): Foo => x;']],
    ['3 flags a block-bodied identity with a single return', ['const asT = (x: number) => { return x; };']],
    [
      '4 flags function declaration and object method identities',
      ['function asNumber(x: number) { return x; }', 'const o = { id(x: number) { return x; } };'],
    ],
  ];

  test.for(cases)('6.1.%s', ([, codes], { expectEachToReport, lintRule }) => {
    expectEachToReport(lintRule, codes, 'noIdentityCast');
  });
});

describe('6.2 permitting genuine pass-throughs and transforming bodies', () => {
  const cases: IdentityCastCase[] = [
    [
      '1 allows a generic identity, plain or constrained — the sanctioned pass-through',
      ['const identity = <T>(x: T) => x;', 'const identity = <T extends object>(x: T) => x;'],
    ],
    ['2 allows an untyped parameter, which asserts no type', ['const echo = (x) => x;']],
    [
      '3 allows a body that transforms the argument or returns a property',
      ['const double = (x: number) => x * 2;', 'const first = (x: { a: number }) => x.a;'],
    ],
    [
      '4 allows more than one parameter and a block body that does more than return',
      ['const keepFirst = (a: number, b: number) => a;', 'const relay = (x: number) => { log(x); return x; };'],
    ],
  ];

  test.for(cases)('6.2.%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});
