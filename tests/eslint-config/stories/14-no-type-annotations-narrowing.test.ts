import type { Linter } from 'eslint';

import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-type-annotations' });

const narrowingOnly = { options: [{ narrowing: true, redundant: false }] };

type ApplySuggestion = (code: string, message: Linter.LintMessage) => string;
type RuleLint = (code: string, lintOptions?: { options?: unknown[] }) => Linter.LintMessage[];

const expectRemovableNarrowing = (
  lintRule: RuleLint,
  applySuggestion: ApplySuggestion,
  code: string,
  messageId: 'narrowReturnType' | 'narrowVarType',
  unannotated: string,
) => {
  const messages = lintRule(code, narrowingOnly);
  expect(messages).toMatchObject([{ messageId, suggestions: [{ messageId: 'removeAnnotation' }] }]);
  const [message] = messages;
  if (message === undefined) throw new Error('expected a narrowing report');
  expect(applySuggestion(code, message)).toBe(unannotated);
};

describe('14.1 flagging variable annotations that hide members of their initializer', () => {
  test('14.1.1 flags a variable type hiding one or several members, suggesting removal', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; const slim = wide;',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number; c: number }; const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number; c: number }; const slim = wide;',
    );
  });

  test('14.1.2 flags hiding a member declared on a named interface, in source or annotation position', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'interface Wide { a: number; b: number } declare const w: Wide; const slim: { a: number } = w;',
      'narrowVarType',
      'interface Wide { a: number; b: number } declare const w: Wide; const slim = w;',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s: Slim = w;',
      'narrowVarType',
      'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s = w;',
    );
  });

  test('14.1.3 flags call-expression and member-access initializers', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare function make(): { a: number; b: number }; const slim: { a: number } = make();',
      'narrowVarType',
      'declare function make(): { a: number; b: number }; const slim = make();',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const box: { inner: { a: number; b: number } }; const slim: { a: number } = box.inner;',
      'narrowVarType',
      'declare const box: { inner: { a: number; b: number } }; const slim = box.inner;',
    );
  });

  test('14.1.4 flags a never-reassigned let, which is effectively const', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; let slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; let slim = wide;',
    );
  });

  test('14.1.5 flags upcasting a class instance to a subset of its members', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'class Cat { move() {} meow() {} } declare const c: Cat; const a: { move(): void } = c;',
      'narrowVarType',
      'class Cat { move() {} meow() {} } declare const c: Cat; const a = c;',
    );
  });

  test('14.1.6 flags readonly fictions over fresh mutable collections', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'const seen: ReadonlySet<string> = new Set(["a"]);',
      'narrowVarType',
      'const seen = new Set(["a"]);',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const arr: number[]; const ro: readonly number[] = arr;',
      'narrowVarType',
      'declare const arr: number[]; const ro = arr;',
    );
  });

  test('14.1.7 flags a bare function-type annotation hiding a property of the callable value', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { (x: number): void; extra: number }; const f: (x: number) => void = wide;',
      'narrowVarType',
      'declare const wide: { (x: number): void; extra: number }; const f = wide;',
    );
  });
});

describe('14.2 flagging return annotations that hide members of the returned value', () => {
  test('14.2.1 flags concise and block-bodied arrow return types', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; const get = (): { a: number } => wide;',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; const get = () => wide;',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; const f = (): { a: number } => { return wide; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; const f = () => { return wide; };',
    );
  });

  test('14.2.2 flags function declaration and method return types', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; function f(): { a: number } { return wide; }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; function f() { return wide; }',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'class A { m(w: { a: number; b: number }): { a: number } { return w; } }',
      'narrowReturnType',
      'class A { m(w: { a: number; b: number }) { return w; } }',
    );
  });

  test('14.2.3 flags a member common to every return that the return type hides', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
      'narrowReturnType',
      'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean) => { if (cond) return x; return y; };',
    );
  });

  test('14.2.4 does not mistake the returns of a nested function for the outer return', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = (): { a: number } => { const g = () => { return partial; }; return wide; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = () => { const g = () => { return partial; }; return wide; };',
    );
  });

  test('14.2.5 flags a nested arrow inside an exported boundary, which is still internal', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export const outer = () => { const g = (): { a: number } => wide; return g; };',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export const outer = () => { const g = () => wide; return g; };',
    );
  });

  test('14.2.6 flags a function-type return annotation hiding a property of the returned callable value', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = (): Fn => wide;',
      'narrowReturnType',
      'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = () => wide;',
    );
  });
});

describe('14.3 flagging module boundaries all the same', () => {
  test('14.3.1 flags exported arrows, variables, and re-exported variables', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export const get = (): { a: number } => wide;',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export const get = () => wide;',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export const slim: { a: number } = wide;',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; export const slim = wide;',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;\nexport { slim };',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; const slim = wide;\nexport { slim };',
    );
  });

  test('14.3.2 flags exported function declarations and methods of exported classes', ({
    applySuggestion,
    lintRule,
  }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export function f(): { a: number } { return wide; }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export function f() { return wide; }',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export class C { m(): { a: number } { return wide; } }',
      'narrowReturnType',
      'declare const wide: { a: number; b: number }; export class C { m() { return wide; } }',
    );
  });
});

describe('14.4 flagging class field annotations that hide members of their initializer', () => {
  test('14.4.1 flags mutable, readonly, and exported-class fields alike', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; class C { field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; class C { field = wide; }',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; class C { readonly field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; class C { readonly field = wide; }',
    );
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'declare const wide: { a: number; b: number }; export class C { field: { a: number } = wide; }',
      'narrowVarType',
      'declare const wide: { a: number; b: number }; export class C { field = wide; }',
    );
  });

  test('14.4.2 flags a class field typed as ReadonlySet over a fresh mutable Set', ({ applySuggestion, lintRule }) => {
    expectRemovableNarrowing(
      lintRule,
      applySuggestion,
      'class C { seen: ReadonlySet<string> = new Set(["a"]); }',
      'narrowVarType',
      'class C { seen = new Set(["a"]); }',
    );
  });
});

describe('14.5 permitting annotations that hide nothing', () => {
  test('14.5.1 allows an annotation matching the value exactly, for variables and class fields', ({ lintRule }) => {
    expect(
      lintRule(
        'declare const exact: { a: number; b: number }; const x: { a: number; b: number } = exact;',
        narrowingOnly,
      ),
    ).toHaveLength(0);
    expect(
      lintRule(
        'declare const exact: { a: number; b: number }; class C { field: { a: number; b: number } = exact; }',
        narrowingOnly,
      ),
    ).toHaveLength(0);
  });

  test('14.5.2 allows widening literals and array element types', ({ lintRule }) => {
    expect(lintRule('const x: number = 5;', narrowingOnly)).toHaveLength(0);
    expect(lintRule('declare const lit: "a"; const x: string = lit;', narrowingOnly)).toHaveLength(0);
    expect(
      lintRule('declare const arr: number[]; const widened: (number | string)[] = arr;', narrowingOnly),
    ).toHaveLength(0);
    expect(lintRule('class C { count: number = 5; }', narrowingOnly)).toHaveLength(0);
  });

  test('14.5.3 allows erasing to unknown and open index-signature dictionaries', ({ lintRule }) => {
    expect(lintRule('const x: unknown = { a: 1, b: 2 };', narrowingOnly)).toHaveLength(0);
    expect(
      lintRule(
        'declare const wide: { a: number; b: number }; const dict: { [k: string]: number } = wide;',
        narrowingOnly,
      ),
    ).toHaveLength(0);
  });

  test('14.5.4 allows a member missing from some return branch, which is not common to all returns', ({ lintRule }) => {
    expect(
      lintRule(
        'declare const x: { a: number; b: number }; declare const y: { a: number; c: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
        narrowingOnly,
      ),
    ).toHaveLength(0);
  });

  test('14.5.5 leaves async return types alone, whose body type is the resolved value', ({ lintRule }) => {
    expect(
      lintRule(
        'declare const wide: { a: number; b: number }; const f = async (): Promise<{ a: number }> => wide;',
        narrowingOnly,
      ),
    ).toHaveLength(0);
  });
});

describe('14.6 permitting annotations the workaround cannot replace', () => {
  test('14.6.1 allows a reassigned let and a class field reassigned to a narrower value', ({ lintRule }) => {
    expect(
      lintRule(
        'declare const wide: { a: number; b: number }; declare const slim: { a: number }; let x: { a: number } = wide; x = slim;',
        narrowingOnly,
      ),
    ).toHaveLength(0);
    expect(
      lintRule(
        'declare const wide: { a: number; b: number }; declare const slim: { a: number }; class C { field: { a: number } = wide; m() { this.field = slim; } }',
        narrowingOnly,
      ),
    ).toHaveLength(0);
  });

  test('14.6.2 allows recursive arrows and generic returns referencing a type parameter', ({ lintRule }) => {
    expect(
      lintRule(
        'declare const wide: { a: number; b: number }; const f = (n: number): { a: number } => n > 0 ? wide : f(n - 1);',
        narrowingOnly,
      ),
    ).toHaveLength(0);
    expect(lintRule('const wrap = <T>(x: T): { value: T } => ({ value: x });', narrowingOnly)).toHaveLength(0);
  });

  test('14.6.3 allows an object literal that matches its annotation', ({ lintRule }) => {
    expect(lintRule('const p: { x: number } = { x: 1 };', narrowingOnly)).toHaveLength(0);
  });

  test('14.6.4 allows function-type annotations over plain function values that hide nothing', ({ lintRule }) => {
    expect(
      lintRule(
        'type Ctx = { id: string }; type StrictCreate = (context: Ctx) => Record<string, () => void>; const create: StrictCreate = context => ({});',
        narrowingOnly,
      ),
    ).toHaveLength(0);
    expect(
      lintRule('declare const fn: (x: number) => void; const g: (x: number) => void = fn;', narrowingOnly),
    ).toHaveLength(0);
  });
});
