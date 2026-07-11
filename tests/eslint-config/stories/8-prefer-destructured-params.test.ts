import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'prefer-destructured-params' });

type FixCase = [shape: string, pairs: [code: string, expected: string][], expectLintReport?: true];

describe('8.1 rewriting property-only parameters into destructuring patterns', () => {
  const cases: FixCase[] = [
    [
      '8.1.1 rewrites a single property read in a concise body',
      [['const first = (node: Foo) => node.parent;', 'const first = ({ parent }: Foo) => parent;']],
      true,
    ],
    [
      '8.1.2 turns several distinct properties into several bindings and a repeated read into one',
      [
        ['const sum = (node: Foo) => node.a + node.b;', 'const sum = ({ a, b }: Foo) => a + b;'],
        ['const twice = (node: Foo) => node.x + node.x;', 'const twice = ({ x }: Foo) => x + x;'],
      ],
    ],
    [
      '8.1.3 rewrites function declaration and object method parameters',
      [
        ['function read(node: Foo) { return node.value; }', 'function read({ value }: Foo) { return value; }'],
        [
          'const obj = { read(node: Foo) { return node.value; } };',
          'const obj = { read({ value }: Foo) { return value; } };',
        ],
      ],
    ],
    [
      '8.1.4 absorbs a const alias whose name already matches the property',
      [
        [
          ['const getName = (node: Foo) => {', '  const parent = node.parent;', '  return parent.id;', '};'].join('\n'),
          ['const getName = ({ parent }: Foo) => {', '  return parent.id;', '};'].join('\n'),
        ],
      ],
    ],
    [
      '8.1.5 absorbs a const alias under a different name, renaming its references to the property',
      [
        [
          [
            'const check = (node: Foo) => {',
            '  const decl = node.parent;',
            '  return decl.type && decl.id;',
            '};',
          ].join('\n'),
          ['const check = ({ parent }: Foo) => {', '  return parent.type && parent.id;', '};'].join('\n'),
        ],
      ],
    ],
    [
      '8.1.6 combines an alias and a direct read into one pattern',
      [
        [
          ['const mix = (node: Foo) => {', '  const x = node.x;', '  return x + node.y;', '};'].join('\n'),
          ['const mix = ({ x, y }: Foo) => {', '  return x + y;', '};'].join('\n'),
        ],
      ],
    ],
    [
      '8.1.7 treats a non-const alias as a direct read, leaving the local binding in place',
      [
        [
          'const keep = (node: Foo) => { let x = node.y; return x; };',
          'const keep = ({ y }: Foo) => { let x = y; return x; };',
        ],
      ],
    ],
    [
      '8.1.8 destructures only the property-only parameter, leaving a method-receiver parameter alone',
      [
        [
          [
            'const reExported = (node: Foo, set: Bar) => {',
            '  if (set.size === 0) return false;',
            '  const decl = node.parent;',
            '  return decl.type && set.has(decl.id);',
            '};',
          ].join('\n'),
          [
            'const reExported = ({ parent }: Foo, set: Bar) => {',
            '  if (set.size === 0) return false;',
            '  return parent.type && set.has(parent.id);',
            '};',
          ].join('\n'),
        ],
      ],
    ],
  ];

  test.for(cases)('%s', ([, pairs, expectLintReport], { fixRule, lintRule }) => {
    for (const [code, expected] of pairs) {
      if (expectLintReport === true) expect(lintRule(code)).toReport('destructureParameter');
      expect(fixRule(code)).toBe(expected);
    }
  });
});

type LintCase = [shape: string, codes: string[]];

describe('8.2 reporting without an autofix when destructuring would collide', () => {
  const cases: LintCase[] = [
    [
      '8.2.1 reports a collision with a function-scoped local without offering an autofix',
      [['const collide = (node: Foo) => {', '  const parent = 1;', '  return node.parent + parent;', '};'].join('\n')],
    ],
    [
      '8.2.2 reports a same-named local alias clash without offering an autofix',
      ['const shadow = (node: Foo) => { let parent = node.parent; return parent; };'],
    ],
    [
      '8.2.3 reports a collision with a nested-scope binding without offering an autofix',
      ['const each = (node: Foo) => node.item.map(item => item);'],
    ],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReport, lintRule }) => {
    expectEachToReport(lintRule, codes, 'destructureParameterNoFix');
  });
});

describe('8.3 permitting parameters that need their whole object', () => {
  const cases: LintCase[] = [
    ['8.3.1 leaves an untyped parameter alone', ['const inferred = (node) => node.parent;']],
    [
      '8.3.2 leaves two parameters that would destructure to the same name alone',
      ['const pairwise = (left: Foo, right: Foo) => left.member === right.member;'],
    ],
    [
      '8.3.3 leaves a whole object that is returned, passed on, or compared alone',
      [
        'const identity = (node: Foo) => node;',
        'const pass = (node: Foo) => use(node);',
        'const both = (node: Foo) => node.x === node;',
      ],
    ],
    [
      '8.3.4 leaves method calls, computed access, and optional access alone',
      [
        'const call = (node: Foo) => node.run();',
        'const indexed = (node: Foo, key: string) => node[key];',
        'const maybe = (node: Foo) => node?.parent;',
      ],
    ],
    [
      '8.3.5 leaves member writes, reserved-word properties, and already-destructured parameters alone',
      [
        'const write = (node: Foo) => { node.x = 1; };',
        'const reserved = (node: Foo) => node.default;',
        'const destructured = ({ parent }: Foo) => parent;',
      ],
    ],
    [
      '8.3.7 leaves a union-typed parameter whose property read depends on narrowing alone',
      [
        [
          'type Wide = { kind: "wide"; span: number };',
          'type Slim = { kind: "slim" };',
          'const isWideSpan = (node: Slim | Wide) => node.kind === "wide" && node.span > 0;',
        ].join('\n'),
      ],
    ],
    [
      '8.3.6 leaves an unused parameter and a free-variable capture alone',
      [
        'const unused = (node: Foo) => 1;',
        ['const capture = (node: Foo) => {', '  return node.helper + helper();', '};'].join('\n'),
      ],
    ],
  ];

  test.for(cases)('%s', ([, codes], { expectEachToReportNothing, lintRule }) => {
    expectEachToReportNothing(lintRule, codes);
  });
});
