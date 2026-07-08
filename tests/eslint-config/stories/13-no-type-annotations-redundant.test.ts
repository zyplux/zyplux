import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-type-annotations' });

const redundantOnly = { options: [{ narrowing: false, redundant: true }] };
const returnReport = [{ messageId: 'removeReturnType' }];
const paramReport = [{ messageId: 'removeParamType' }];
const varReport = [{ messageId: 'removeVarType' }];

describe('13.1 removing redundant arrow return types', () => {
  test('13.1.1 removes an inferrable arrow return type, standalone or as an object property', ({
    fixRule,
    lintRule,
  }) => {
    expect(lintRule('const greet = (): string => "hi";', redundantOnly)).toMatchObject(returnReport);
    expect(fixRule('const greet = (): string => "hi";', redundantOnly)).toBe('const greet = () => "hi";');
    expect(fixRule('const obj = { greet: (): string => "hi" };', redundantOnly)).toBe(
      'const obj = { greet: () => "hi" };',
    );
  });

  test('13.1.2 removes a return type despite a default parameter value or an as const literal', ({ fixRule }) => {
    expect(fixRule('const f = (x: number = 0): number => x;', redundantOnly)).toBe('const f = (x: number = 0) => x;');
    expect(fixRule('const f = (): readonly [number, string] => [1, "a"] as const;', redundantOnly)).toBe(
      'const f = () => [1, "a"] as const;',
    );
  });

  test('13.1.3 removes the return type of a nested arrow inside an exported boundary', ({ fixRule }) => {
    expect(fixRule('export const f = () => { const g = (): number => 1; return g; };', redundantOnly)).toBe(
      'export const f = () => { const g = () => 1; return g; };',
    );
  });
});

describe('13.2 removing redundant parameter types', () => {
  test('13.2.1 removes a callback parameter type fixed by its contextual type', ({ fixRule, lintRule }) => {
    expect(lintRule('const doubled = [1, 2, 3].map((n: number) => n * 2);', redundantOnly)).toMatchObject(paramReport);
    expect(fixRule('const doubled = [1, 2, 3].map((n: number) => n * 2);', redundantOnly)).toBe(
      'const doubled = [1, 2, 3].map((n) => n * 2);',
    );
  });

  test('13.2.2 removes a parameter type that restates the declared function type, keeping the variable annotation', ({
    fixRule,
  }) => {
    expect(fixRule('const handler: (a: number) => void = (a: number) => { a; };', redundantOnly)).toBe(
      'const handler: (a: number) => void = (a) => { a; };',
    );
  });

  test('13.2.3 removes both a redundant return type and a contextual parameter on the same callback', ({
    fixRule,
    lintRule,
  }) => {
    const code = 'const run = (cb: (x: number) => number) => cb(1); run((x: number): number => x);';
    expect(lintRule(code, redundantOnly)).toMatchObject([
      { messageId: 'removeParamType' },
      { messageId: 'removeReturnType' },
    ]);
    expect(fixRule(code, redundantOnly)).toBe('const run = (cb: (x: number) => number) => cb(1); run((x) => x);');
  });
});

describe('13.3 removing variable and class field types that restate their initializers', () => {
  test('13.3.1 removes annotations restating identifier and member-access initializers', ({ fixRule, lintRule }) => {
    expect(lintRule('declare const label: string; const copy: string = label;', redundantOnly)).toMatchObject(
      varReport,
    );
    expect(fixRule('declare const label: string; const copy: string = label;', redundantOnly)).toBe(
      'declare const label: string; const copy = label;',
    );
    expect(fixRule('declare const box: { count: number }; const n: number = box.count;', redundantOnly)).toBe(
      'declare const box: { count: number }; const n = box.count;',
    );
  });

  test('13.3.2 removes annotations restating binary, unary, and template-literal initializers', ({ fixRule }) => {
    expect(fixRule('declare const a: number; declare const b: number; const sum: number = a + b;', redundantOnly)).toBe(
      'declare const a: number; declare const b: number; const sum = a + b;',
    );
    expect(fixRule('declare const ready: boolean; const blocked: boolean = !ready;', redundantOnly)).toBe(
      'declare const ready: boolean; const blocked = !ready;',
    );
    expect(fixRule('declare const name: string; const greeting: string = `hi ${name}`;', redundantOnly)).toBe(
      'declare const name: string; const greeting = `hi ${name}`;',
    );
  });

  test('13.3.3 removes an annotation restating a named interface type from an identifier initializer', ({
    fixRule,
  }) => {
    expect(
      fixRule('interface Dog { bark(): void } declare const pet: Dog; const mine: Dog = pet;', redundantOnly),
    ).toBe('interface Dog { bark(): void } declare const pet: Dog; const mine = pet;');
  });

  test('13.3.4 removes a class property annotation restating its initializer', ({ fixRule }) => {
    expect(fixRule('declare const seed: number; class Counter { value: number = seed; }', redundantOnly)).toBe(
      'declare const seed: number; class Counter { value = seed; }',
    );
  });
});

describe('13.4 keeping load-bearing parameter annotations', () => {
  test('13.4.1 keeps a standalone parameter annotation, which has no contextual type', ({ lintRule }) => {
    expect(lintRule('const f = (x: number) => x;', redundantOnly)).toHaveLength(0);
  });

  test('13.4.2 keeps annotations whose contextual type merely echoes them through generic inference', ({
    lintRule,
  }) => {
    expect(
      lintRule(
        'type Opt = { a?: number }; const make = (o: Opt = {}) => [o]; const z = Object.assign(make, { withDefaults: (defaults: Opt) => (options: Opt = {}) => make({ ...defaults, ...options }) });',
        redundantOnly,
      ),
    ).toHaveLength(0);
    expect(
      lintRule('declare function pipe<A>(f: (a: A) => void): void; pipe((x: number) => { void x; });', redundantOnly),
    ).toHaveLength(0);
  });

  test('13.4.3 keeps a parameter that deliberately widens past the contextual type', ({ lintRule }) => {
    expect(
      lintRule('const widen = (cb: (x: 1 | 2) => void) => cb(1); widen((x: number) => {});', redundantOnly),
    ).toHaveLength(0);
  });
});

describe('13.5 keeping return annotations at module boundaries and special returns', () => {
  test('13.5.1 keeps a type predicate return', ({ lintRule }) => {
    expect(
      lintRule('const isString = (x: unknown): x is string => typeof x === "string";', redundantOnly),
    ).toHaveLength(0);
  });

  test('13.5.2 keeps annotations on exported, default-exported, and re-exported arrows', ({ lintRule }) => {
    expect(lintRule('export const greet = (): string => "hi";', redundantOnly)).toHaveLength(0);
    expect(lintRule('export default (): string => "hi";', redundantOnly)).toHaveLength(0);
    expect(lintRule('const greet = (): string => "hi";\nexport { greet };', redundantOnly)).toHaveLength(0);
    expect(lintRule('export const handler: (a: number) => void = (a: number) => {};', redundantOnly)).toHaveLength(0);
  });

  test('13.5.3 keeps a recursive arrow return and a generic return that inference would widen', ({ lintRule }) => {
    expect(
      lintRule('const factorial = (n: number): number => n <= 1 ? 1 : n * factorial(n - 1);', redundantOnly),
    ).toHaveLength(0);
    expect(
      lintRule(
        [
          'type Result<T> = { error: false; value: T } | { error: true; message: string };',
          'const ok = <T>(value: T): Result<T> => ({ error: false, value });',
          'const r = ok(42);',
          'const out = r.error ? r.message : `got ${r.value}`;',
        ].join('\n'),
        redundantOnly,
      ),
    ).toHaveLength(0);
  });
});

describe('13.6 keeping load-bearing variable annotations', () => {
  test('13.6.1 keeps annotations that widen their initializer', ({ lintRule }) => {
    expect(lintRule('declare const small: 1; const widened: number = small;', redundantOnly)).toHaveLength(0);
    expect(lintRule('let pending: number | undefined = undefined;', redundantOnly)).toHaveLength(0);
  });

  test('13.6.2 keeps annotations over new, call, object-literal, and empty-array initializers', ({ lintRule }) => {
    expect(lintRule('const s: Set<number> = new Set();', redundantOnly)).toHaveLength(0);
    expect(
      lintRule('declare function makeSet(): Set<number>; const s: Set<number> = makeSet();', redundantOnly),
    ).toHaveLength(0);
    expect(lintRule('const point: { x: number } = { x: 1 };', redundantOnly)).toHaveLength(0);
    expect(lintRule('const items: number[] = [];', redundantOnly)).toHaveLength(0);
  });

  test('13.6.3 keeps annotations on exported and re-exported variables', ({ lintRule }) => {
    expect(lintRule('declare const label: string; export const copy: string = label;', redundantOnly)).toHaveLength(0);
    expect(
      lintRule('declare const label: string; const copy: string = label;\nexport { copy };', redundantOnly),
    ).toHaveLength(0);
  });
});

describe('13.7 confining redundancy checks to arrows', () => {
  test('13.7.1 leaves class members and ambient declarations alone', ({ lintRule }) => {
    expect(lintRule('class A { m(x: number): number { return x; } }', redundantOnly)).toHaveLength(0);
    expect(lintRule('declare function exists(): number;', redundantOnly)).toHaveLength(0);
    expect(lintRule('declare class C { m(): number; }', redundantOnly)).toHaveLength(0);
  });

  test('13.7.2 leaves function declarations, expressions, and generators alone', ({ lintRule }) => {
    expect(lintRule('async function fetchAll(): Promise<void> {}', redundantOnly)).toHaveLength(0);
    expect(lintRule('const greet = function(): string { return "hi"; };', redundantOnly)).toHaveLength(0);
    expect(lintRule('function compute(): number { const x = 1; return x; }', redundantOnly)).toHaveLength(0);
    expect(lintRule('function* gen(): Generator<number> { yield 1; }', redundantOnly)).toHaveLength(0);
  });

  test('13.7.3 leaves getters, method shorthands, interface signatures, and constructors alone', ({ lintRule }) => {
    expect(lintRule('class A { get x(): number { return 1; } }', redundantOnly)).toHaveLength(0);
    expect(lintRule('const obj = { greet(): string { return "hi"; } };', redundantOnly)).toHaveLength(0);
    expect(lintRule('interface I { greet(): string; }', redundantOnly)).toHaveLength(0);
    expect(lintRule('class A { constructor(public n: number) {} }', redundantOnly)).toHaveLength(0);
  });
});
