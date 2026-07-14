import type { Linter } from '#fixtures';

import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-type-annotations' });

const narrowingOnly = { options: [{ narrowing: true, redundant: false }] };

type ApplySuggestion = (code: string, message: Linter.LintMessage) => string;
type LintFixtures = { lintRule: RuleLint };
type MessageId = 'narrowReturnType' | 'narrowVarType';
type NarrowingCase = [shape: string, code: string, messageId: MessageId, unannotated: string];
type NarrowingFixtures = { applySuggestion: ApplySuggestion; lintRule: RuleLint };
type RuleLint = (code: string, lintOptions?: { options?: unknown[] }) => Linter.LintMessage[];

const expectRemovableNarrowing = (
  lintRule: RuleLint,
  applySuggestion: ApplySuggestion,
  code: string,
  messageId: MessageId,
  unannotated: string,
) => {
  const messages = lintRule(code, narrowingOnly);
  expect(messages).toMatchObject([{ messageId, suggestions: [{ messageId: 'removeAnnotation' }] }]);
  const [message] = messages;
  if (message === undefined) throw new Error('expected a narrowing report');
  expect(applySuggestion(code, message)).toBe(unannotated);
};

const runNarrowingCase = (
  [, code, messageId, unannotated]: NarrowingCase,
  { applySuggestion, lintRule }: NarrowingFixtures,
) => {
  expectRemovableNarrowing(lintRule, applySuggestion, code, messageId, unannotated);
};

describe('14.1 flagging variable annotations that hide members of their initializer', () => {
  const cases: NarrowingCase[] = [
    [
      '1 flags a variable type hiding one member, suggesting removal',
      'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; const slim = wide;',
    ],
    [
      '2 flags a variable type hiding several members, suggesting removal',
      'declare const wide: { a: number; b: number; c: number }; const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number; c: number }; const slim = wide;',
    ],
    [
      '3 flags hiding a member declared on a named interface in source position',
      'interface Wide { a: number; b: number } declare const w: Wide; const slim: { a: number } = w;',
      'narrowVarType',
      'interface Wide { a: number; b: number } declare const w: Wide; const slim = w;',
    ],
    [
      '4 flags hiding a member declared on a named interface in annotation position',
      'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s: Slim = w;',
      'narrowVarType',
      'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s = w;',
    ],
    [
      '5 flags a call-expression initializer',
      'declare function make(): { a: number; b: number }; const slim: { a: number } = make();',
      'narrowVarType',
      'declare function make(): { a: number; b: number }; const slim = make();',
    ],
    [
      '6 flags a member-access initializer',
      'declare const box: { inner: { a: number; b: number } }; const slim: { a: number } = box.inner;',
      'narrowVarType',
      'declare const box: { inner: { a: number; b: number } }; const slim = box.inner;',
    ],
    [
      '7 flags a never-reassigned let, which is effectively const',
      'declare const wide: { a: number; b: number }; let slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; let slim = wide;',
    ],
    [
      '8 flags upcasting a class instance to a subset of its members',
      'class Cat { move() {} meow() {} } declare const c: Cat; const a: { move(): void } = c;',
      'narrowVarType',
      'class Cat { move() {} meow() {} } declare const c: Cat; const a = c;',
    ],
    [
      '9 flags a readonly fiction over a fresh mutable Set',
      'const seen: ReadonlySet<string> = new Set(["a"]);',
      'narrowVarType',
      'const seen = new Set(["a"]);',
    ],
    [
      '10 flags a readonly fiction over a mutable array',
      'declare const arr: number[]; const ro: readonly number[] = arr;',
      'narrowVarType',
      'declare const arr: number[]; const ro = arr;',
    ],
    [
      '11 flags a bare function-type annotation hiding a property of the callable value',
      'declare const wide: { (x: number): void; extra: number }; const f: (x: number) => void = wide;',
      'narrowVarType',
      'declare const wide: { (x: number): void; extra: number }; const f = wide;',
    ],
  ];

  test.for(cases)('14.1.%s', runNarrowingCase);
});

describe('14.2 flagging return annotations that hide members of the returned value', () => {
  const cases: NarrowingCase[] = [
    [
      '1 flags a concise arrow return type',
      'declare const wide: { a: number; b: number }; const get = (): { a: number } => wide;',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; const get = () => wide;',
    ],
    [
      '2 flags a block-bodied arrow return type',
      'declare const wide: { a: number; b: number }; const f = (): { a: number } => { return wide; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; const f = () => { return wide; };',
    ],
    [
      '3 flags a function declaration return type',
      'declare const wide: { a: number; b: number }; function f(): { a: number } { return wide; }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; function f() { return wide; }',
    ],
    [
      '4 flags a method return type',
      'class A { m(w: { a: number; b: number }): { a: number } { return w; } }',
      'narrowReturnType',
      'class A { m(w: { a: number; b: number }) { return w; } }',
    ],
    [
      '5 flags a member common to every return that the return type hides',
      'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
      'narrowReturnType',
      'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean) => { if (cond) return x; return y; };',
    ],
    [
      '6 does not mistake the returns of a nested function for the outer return',
      'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = (): { a: number } => { const g = () => { return partial; }; return wide; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = () => { const g = () => { return partial; }; return wide; };',
    ],
    [
      '7 flags a nested arrow inside an exported boundary, which is still internal',
      'declare const wide: { a: number; b: number }; export const outer = () => { const g = (): { a: number } => wide; return g; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export const outer = () => { const g = () => wide; return g; };',
    ],
    [
      '8 flags a function-type return annotation hiding a property of the returned callable value',
      'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = (): Fn => wide;',
      'narrowReturnType',
      'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = () => wide;',
    ],
  ];

  test.for(cases)('14.2.%s', runNarrowingCase);
});

describe('14.3 flagging module boundaries all the same', () => {
  const cases: NarrowingCase[] = [
    [
      '1 flags an exported arrow return type',
      'declare const wide: { a: number; b: number }; export const get = (): { a: number } => wide;',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export const get = () => wide;',
    ],
    [
      '2 flags an exported variable annotation',
      'declare const wide: { a: number; b: number }; export const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; export const slim = wide;',
    ],
    [
      '3 flags a re-exported variable annotation',
      'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;\nexport { slim };',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; const slim = wide;\nexport { slim };',
    ],
    [
      '4 flags an exported function declaration return type',
      'declare const wide: { a: number; b: number }; export function f(): { a: number } { return wide; }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export function f() { return wide; }',
    ],
    [
      '5 flags a method return type of an exported class',
      'declare const wide: { a: number; b: number }; export class C { m(): { a: number } { return wide; } }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export class C { m() { return wide; } }',
    ],
  ];

  test.for(cases)('14.3.%s', runNarrowingCase);
});

describe('14.4 flagging class field annotations that hide members of their initializer', () => {
  const cases: NarrowingCase[] = [
    [
      '1 flags a mutable class field',
      'declare const wide: { a: number; b: number }; class C { field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; class C { field = wide; }',
    ],
    [
      '2 flags a readonly class field',
      'declare const wide: { a: number; b: number }; class C { readonly field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; class C { readonly field = wide; }',
    ],
    [
      '3 flags a field of an exported class',
      'declare const wide: { a: number; b: number }; export class C { field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; export class C { field = wide; }',
    ],
    [
      '4 flags a class field typed as ReadonlySet over a fresh mutable Set',
      'class C { seen: ReadonlySet<string> = new Set(["a"]); }',
      'narrowVarType',
      'class C { seen = new Set(["a"]); }',
    ],
  ];

  test.for(cases)('14.4.%s', runNarrowingCase);
});

type ReportNothingCase = [shape: string, code: string];

const runReportNothingCase = ([, code]: ReportNothingCase, { lintRule }: LintFixtures) => {
  expect(lintRule(code, narrowingOnly)).toReportNothing();
};

describe('14.5 permitting annotations that hide nothing', () => {
  test.for<ReportNothingCase>([
    [
      '1 allows an annotation matching the value exactly for a variable',
      'declare const exact: { a: number; b: number }; const x: { a: number; b: number } = exact;',
    ],
    [
      '2 allows an annotation matching the value exactly for a class field',
      'declare const exact: { a: number; b: number }; class C { field: { a: number; b: number } = exact; }',
    ],
    ['3 allows widening a literal type', 'const x: number = 5;'],
    ['4 allows widening a literal initializer type', 'declare const lit: "a"; const x: string = lit;'],
    ['5 allows widening array element types', 'declare const arr: number[]; const widened: (number | string)[] = arr;'],
    ['6 allows widening a class field literal type', 'class C { count: number = 5; }'],
    ['7 allows erasing to unknown', 'const x: unknown = { a: 1, b: 2 };'],
    [
      '8 allows an open index-signature dictionary',
      'declare const wide: { a: number; b: number }; const dict: { [k: string]: number } = wide;',
    ],
    [
      '9 allows a member missing from some return branch, which is not common to all returns',
      'declare const x: { a: number; b: number }; declare const y: { a: number; c: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
    ],
    [
      '10 leaves async return types alone, whose body type is the resolved value',
      'declare const wide: { a: number; b: number }; const f = async (): Promise<{ a: number }> => wide;',
    ],
  ])('14.5.%s', runReportNothingCase);
});

describe('14.6 permitting annotations the workaround cannot replace', () => {
  test.for<ReportNothingCase>([
    [
      '1 allows a reassigned let',
      'declare const wide: { a: number; b: number }; declare const slim: { a: number }; let x: { a: number } = wide; x = slim;',
    ],
    [
      '2 allows a class field reassigned to a narrower value',
      'declare const wide: { a: number; b: number }; declare const slim: { a: number }; class C { field: { a: number } = wide; m() { this.field = slim; } }',
    ],
    [
      '3 allows a recursive arrow return',
      'declare const wide: { a: number; b: number }; const f = (n: number): { a: number } => n > 0 ? wide : f(n - 1);',
    ],
    [
      '4 allows a generic return referencing a type parameter',
      'const wrap = <T>(x: T): { value: T } => ({ value: x });',
    ],
    ['5 allows an object literal that matches its annotation', 'const p: { x: number } = { x: 1 };'],
    [
      '6 allows a function-type annotation over a plain function value that hides nothing',
      'type Ctx = { id: string }; type StrictCreate = (context: Ctx) => Record<string, () => void>; const create: StrictCreate = context => ({});',
    ],
    [
      '7 allows a function-type annotation over an identical function type',
      'declare const fn: (x: number) => void; const g: (x: number) => void = fn;',
    ],
  ])('14.6.%s', runReportNothingCase);
});
