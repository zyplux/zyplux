import type { Linter } from '#fixtures';

import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-type-annotations' });

const redundantOnly = { options: [{ narrowing: false, redundant: true }] };

type FixCase = [shape: string, code: string, fixed: string, reportIds?: ReportIds];
type FixFixtures = { fixRule: FixFn; lintRule: LintFn };
type FixFn = (code: string, options?: RuleOptions) => string;
type LintFixtures = { lintRule: LintFn };
type LintFn = (code: string, options?: RuleOptions) => Linter.LintMessage[];
type ReportIds = readonly [string, ...string[]];
type RuleOptions = { options?: unknown[] };

const runFixCase = ([, code, fixed, reportIds]: FixCase, { fixRule, lintRule }: FixFixtures) => {
  if (reportIds !== undefined) expect(lintRule(code, redundantOnly)).toReport(...reportIds);
  expect(fixRule(code, redundantOnly)).toBe(fixed);
};

describe('13.1 removing redundant arrow return types', () => {
  const cases: FixCase[] = [
    [
      '1 removes an inferrable arrow return type, standalone',
      'const greet = (): string => "hi";',
      'const greet = () => "hi";',
      ['removeReturnType'],
    ],
    [
      '2 removes an inferrable arrow return type on an object property',
      'const obj = { greet: (): string => "hi" };',
      'const obj = { greet: () => "hi" };',
    ],
    [
      '3 removes a return type despite a default parameter value',
      'const f = (x: number = 0): number => x;',
      'const f = (x: number = 0) => x;',
    ],
    [
      '4 removes a return type despite an as const literal',
      'const f = (): readonly [number, string] => [1, "a"] as const;',
      'const f = () => [1, "a"] as const;',
    ],
    [
      '5 removes the return type of a nested arrow inside an exported boundary',
      'export const f = () => { const g = (): number => 1; return g; };',
      'export const f = () => { const g = () => 1; return g; };',
    ],
  ];

  test.for(cases)('13.1.%s', runFixCase);
});

describe('13.2 removing redundant parameter types', () => {
  const cases: FixCase[] = [
    [
      '1 removes a callback parameter type fixed by its contextual type',
      'const doubled = [1, 2, 3].map((n: number) => n * 2);',
      'const doubled = [1, 2, 3].map((n) => n * 2);',
      ['removeParamType'],
    ],
    [
      '2 removes a parameter type that restates the declared function type, keeping the variable annotation',
      'const handler: (a: number) => void = (a: number) => { a; };',
      'const handler: (a: number) => void = (a) => { a; };',
    ],
    [
      '3 removes both a redundant return type and a contextual parameter on the same callback',
      'const run = (cb: (x: number) => number) => cb(1); run((x: number): number => x);',
      'const run = (cb: (x: number) => number) => cb(1); run((x) => x);',
      ['removeParamType', 'removeReturnType'],
    ],
  ];

  test.for(cases)('13.2.%s', runFixCase);
});

describe('13.3 removing variable and class field types that restate their initializers', () => {
  const cases: FixCase[] = [
    [
      '1 removes an annotation restating an identifier initializer',
      'declare const label: string; const copy: string = label;',
      'declare const label: string; const copy = label;',
      ['removeVarType'],
    ],
    [
      '2 removes an annotation restating a member-access initializer',
      'declare const box: { count: number }; const n: number = box.count;',
      'declare const box: { count: number }; const n = box.count;',
    ],
    [
      '3 removes an annotation restating a binary initializer',
      'declare const a: number; declare const b: number; const sum: number = a + b;',
      'declare const a: number; declare const b: number; const sum = a + b;',
    ],
    [
      '4 removes an annotation restating a unary initializer',
      'declare const ready: boolean; const blocked: boolean = !ready;',
      'declare const ready: boolean; const blocked = !ready;',
    ],
    [
      '5 removes an annotation restating a template-literal initializer',
      'declare const name: string; const greeting: string = `hi ${name}`;',
      'declare const name: string; const greeting = `hi ${name}`;',
    ],
    [
      '6 removes an annotation restating a named interface type from an identifier initializer',
      'interface Dog { bark(): void } declare const pet: Dog; const mine: Dog = pet;',
      'interface Dog { bark(): void } declare const pet: Dog; const mine = pet;',
    ],
    [
      '7 removes a class property annotation restating its initializer',
      'declare const seed: number; class Counter { value: number = seed; }',
      'declare const seed: number; class Counter { value = seed; }',
    ],
  ];

  test.for(cases)('13.3.%s', runFixCase);
});

type ReportNothingCase = [shape: string, code: string];

const runReportNothingCase = ([, code]: ReportNothingCase, { lintRule }: LintFixtures) => {
  expect(lintRule(code, redundantOnly)).toReportNothing();
};

describe('13.4 keeping load-bearing parameter annotations', () => {
  test.for<ReportNothingCase>([
    ['1 keeps a standalone parameter annotation, which has no contextual type', 'const f = (x: number) => x;'],
    [
      '2 keeps a parameter annotation echoed through generic inference in an object literal',
      'type Opt = { a?: number }; const make = (o: Opt = {}) => [o]; const z = Object.assign(make, { withDefaults: (defaults: Opt) => (options: Opt = {}) => make({ ...defaults, ...options }) });',
    ],
    [
      '3 keeps a parameter annotation echoed through a generic higher order function',
      'declare function pipe<A>(f: (a: A) => void): void; pipe((x: number) => { void x; });',
    ],
    [
      '4 keeps a parameter that deliberately widens past the contextual type',
      'const widen = (cb: (x: 1 | 2) => void) => cb(1); widen((x: number) => {});',
    ],
  ])('13.4.%s', runReportNothingCase);
});

describe('13.5 keeping return annotations at module boundaries and special returns', () => {
  test.for<ReportNothingCase>([
    ['1 keeps a type predicate return', 'const isString = (x: unknown): x is string => typeof x === "string";'],
    ['2 keeps a return type annotation on an exported arrow', 'export const greet = (): string => "hi";'],
    ['3 keeps a return type annotation on a default-exported arrow', 'export default (): string => "hi";'],
    ['4 keeps a return type annotation on a re-exported arrow', 'const greet = (): string => "hi";\nexport { greet };'],
    [
      '5 keeps a parameter type annotation on an exported variable-typed handler',
      'export const handler: (a: number) => void = (a: number) => {};',
    ],
    [
      '6 keeps a recursive arrow return type',
      'const factorial = (n: number): number => n <= 1 ? 1 : n * factorial(n - 1);',
    ],
    [
      '7 keeps a generic return type that inference would widen',
      [
        'type Result<T> = { error: false; value: T } | { error: true; message: string };',
        'const ok = <T>(value: T): Result<T> => ({ error: false, value });',
        'const r = ok(42);',
        'const out = r.error ? r.message : `got ${r.value}`;',
      ].join('\n'),
    ],
  ])('13.5.%s', runReportNothingCase);
});

describe('13.6 keeping load-bearing variable annotations', () => {
  test.for<ReportNothingCase>([
    [
      '1 keeps an annotation that widens a literal initializer',
      'declare const small: 1; const widened: number = small;',
    ],
    ['2 keeps an annotation that widens an undefined initializer', 'let pending: number | undefined = undefined;'],
    ['3 keeps an annotation over a new expression initializer', 'const s: Set<number> = new Set();'],
    [
      '4 keeps an annotation over a call expression initializer',
      'declare function makeSet(): Set<number>; const s: Set<number> = makeSet();',
    ],
    ['5 keeps an annotation over an object-literal initializer', 'const point: { x: number } = { x: 1 };'],
    ['6 keeps an annotation over an empty-array initializer', 'const items: number[] = [];'],
    [
      '7 keeps an annotation on an exported variable',
      'declare const label: string; export const copy: string = label;',
    ],
    [
      '8 keeps an annotation on a re-exported variable',
      'declare const label: string; const copy: string = label;\nexport { copy };',
    ],
  ])('13.6.%s', runReportNothingCase);
});

describe('13.7 confining redundancy checks to arrows', () => {
  test.for<ReportNothingCase>([
    ['1 leaves a class member method alone', 'class A { m(x: number): number { return x; } }'],
    ['2 leaves an ambient function declaration alone', 'declare function exists(): number;'],
    ['3 leaves an ambient class method alone', 'declare class C { m(): number; }'],
    ['4 leaves an async function declaration alone', 'async function fetchAll(): Promise<void> {}'],
    ['5 leaves a function expression alone', 'const greet = function(): string { return "hi"; };'],
    ['6 leaves a function declaration alone', 'function compute(): number { const x = 1; return x; }'],
    ['7 leaves a generator function alone', 'function* gen(): Generator<number> { yield 1; }'],
    ['8 leaves a getter alone', 'class A { get x(): number { return 1; } }'],
    ['9 leaves a method shorthand alone', 'const obj = { greet(): string { return "hi"; } };'],
    ['10 leaves an interface method signature alone', 'interface I { greet(): string; }'],
    ['11 leaves a constructor parameter property alone', 'class A { constructor(public n: number) {} }'],
  ])('13.7.%s', runReportNothingCase);
});
