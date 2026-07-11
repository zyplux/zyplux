import { describe, test } from '#fixtures';

test.override({ ruleName: 'no-anonymous-param-type' });

type NameParamCase = [shape: string, codes: string[], messageIds: [string, ...string[]]];

describe('5.1 flagging inline object types in parameter position', () => {
  const cases: NameParamCase[] = [
    [
      '5.1.1 flags a top-level inline object type on plain and destructured parameters',
      ['const f = (x: { a: string }) => x.a;', 'const f = ({ a }: { a: string }) => a;'],
      ['nameParameterType'],
    ],
    [
      '5.1.2 flags function declaration and object method parameters',
      [
        'function read(opts: { id: number }) { return opts.id; }',
        'const o = { read(p: { x: string }) { return p.x; } };',
      ],
      ['nameParameterType'],
    ],
    [
      '5.1.3 reports each parameter with an inline object type',
      ['const f = (a: { x: string }, b: { y: number }) => a.x;'],
      ['nameParameterType', 'nameParameterType'],
    ],
    [
      '5.1.4 flags an object literal as a union or intersection member',
      ['const f = (x: { a: string } | undefined) => x?.a;', 'const f = (x: Base & { a: string }) => x.a;'],
      ['nameParameterType'],
    ],
    [
      '5.1.5 reports every object literal in a union separately',
      ['const f = (x: { a: string } | { b: number }) => x;'],
      ['nameParameterType', 'nameParameterType'],
    ],
    [
      '5.1.6 flags a parameter with a default value',
      ['const f = (x: { a: string } = { a: "" }) => x.a;'],
      ['nameParameterType'],
    ],
    [
      '5.1.7 flags a constructor parameter property',
      ['class C { constructor(public opts: { a: string }) {} }'],
      ['nameParameterType'],
    ],
  ];

  test.for(cases)('%s', ([, codes, messageIds], { expectEachToReport, lintRule }) => {
    expectEachToReport(lintRule, codes, ...messageIds);
  });
});

type PermitParamCase = [shape: string, codes: string[]];

describe('5.2 permitting named, primitive, and non-parameter object types', () => {
  const cases: PermitParamCase[] = [
    [
      '5.2.1 allows a named type reference, a primitive, and an untyped parameter',
      ['const f = (x: Foo) => x;', 'const f = (x: string) => x;', 'const f = x => x;'],
    ],
    [
      '5.2.2 allows inline object types outside parameter position',
      [
        'const f = (x: string): { a: string } => ({ a: x });',
        'const x: { a: string } = { a: "" };',
        'type T = { a: string };',
      ],
    ],
    [
      '5.2.3 allows an object literal that describes a container element, not the parameter',
      [
        'const f = (rows: { id: string }[]) => rows.length;',
        'const f = (x: Array<{ a: string }>) => x.length;',
        'const f = (x: Record<string, { a: number }>) => x;',
      ],
    ],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});
