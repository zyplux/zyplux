import type { NoTypeAnnotationsOptions } from '#rules/no-type-annotations';

import { noTypeAnnotations } from '#rules/no-type-annotations';

import { typeAwareRuleTester } from './rule-tester';

const narrowingOnly: NoTypeAnnotationsOptions = [{ narrowing: true, redundant: false }];

typeAwareRuleTester.run('no-type-annotations (narrowing)', noTypeAnnotations, {
  invalid: [
    {
      code: 'declare const wide: { a: number; b: number }; const get = (): { a: number } => wide;',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; const get = () => wide;',
            },
          ],
        },
      ],
      name: 'return type hides a member of the returned value',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; const slim = wide;',
            },
          ],
        },
      ],
      name: 'variable type hides a member of its initializer',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number; c: number }; const slim: { a: number } = wide;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number; c: number }; const slim = wide;',
            },
          ],
        },
      ],
      name: 'variable type hides several members at once',
      options: narrowingOnly,
    },
    {
      code: 'interface Wide { a: number; b: number } declare const w: Wide; const slim: { a: number } = w;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'interface Wide { a: number; b: number } declare const w: Wide; const slim = w;',
            },
          ],
        },
      ],
      name: 'variable type hides a member declared on a named interface',
      options: narrowingOnly,
    },
    {
      code: 'declare function make(): { a: number; b: number }; const slim: { a: number } = make();',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare function make(): { a: number; b: number }; const slim = make();',
            },
          ],
        },
      ],
      name: 'variable type hides a member of a call-expression initializer',
      options: narrowingOnly,
    },
    {
      code: 'declare const box: { inner: { a: number; b: number } }; const slim: { a: number } = box.inner;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const box: { inner: { a: number; b: number } }; const slim = box.inner;',
            },
          ],
        },
      ],
      name: 'variable type hides a member of a member-access initializer',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; let slim: { a: number } = wide;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; let slim = wide;',
            },
          ],
        },
      ],
      name: 'a never-reassigned `let` is effectively const, so its narrowing annotation is removable',
      options: narrowingOnly,
    },
    {
      code: 'class Cat { move() {} meow() {} } declare const c: Cat; const a: { move(): void } = c;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'class Cat { move() {} meow() {} } declare const c: Cat; const a = c;',
            },
          ],
        },
      ],
      name: 'upcasting a class instance hides a member it actually has',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export const outer = () => { const g = (): { a: number } => wide; return g; };',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output:
                'declare const wide: { a: number; b: number }; export const outer = () => { const g = () => wide; return g; };',
            },
          ],
        },
      ],
      name: 'a nested arrow inside an exported boundary is still internal',
      options: narrowingOnly,
    },
    {
      code: 'const seen: ReadonlySet<string> = new Set(["a"]);',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [{ messageId: 'removeAnnotation', output: 'const seen = new Set(["a"]);' }],
        },
      ],
      name: 'typing a fresh mutable Set as ReadonlySet is a narrowing anti-pattern, not a readonly value',
      options: narrowingOnly,
    },
    {
      code: 'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s: Slim = w;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output:
                'interface Wide { a: number; b: number } interface Slim { a: number } declare const w: Wide; const s = w;',
            },
          ],
        },
      ],
      name: 'narrowing to a named interface that drops a data field is flagged (no false negative for named types)',
      options: narrowingOnly,
    },
    {
      code: 'declare const arr: number[]; const ro: readonly number[] = arr;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [{ messageId: 'removeAnnotation', output: 'declare const arr: number[]; const ro = arr;' }],
        },
      ],
      name: 'typing a mutable array as readonly is the same anti-pattern as ReadonlySet',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const f = (): { a: number } => { return wide; };',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; const f = () => { return wide; };',
            },
          ],
        },
      ],
      name: 'a block-bodied arrow return type that hides a member is flagged',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; function f(): { a: number } { return wide; }',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; function f() { return wide; }',
            },
          ],
        },
      ],
      name: 'a function declaration return type that hides a member is flagged',
      options: narrowingOnly,
    },
    {
      code: 'class A { m(w: { a: number; b: number }): { a: number } { return w; } }',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            { messageId: 'removeAnnotation', output: 'class A { m(w: { a: number; b: number }) { return w; } }' },
          ],
        },
      ],
      name: 'a method return type that hides a member is flagged',
      options: narrowingOnly,
    },
    {
      code: 'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output:
                'declare const x: { a: number; b: number }; declare const y: { a: number; b: number }; const f = (cond: boolean) => { if (cond) return x; return y; };',
            },
          ],
        },
      ],
      name: 'a member common to every return is hidden by the return type',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = (): { a: number } => { const g = () => { return partial; }; return wide; };',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output:
                'declare const wide: { a: number; b: number }; declare const partial: { a: number }; const f = () => { const g = () => { return partial; }; return wide; };',
            },
          ],
        },
      ],
      name: 'returns of a nested function are not mistaken for the outer return',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export const get = (): { a: number } => wide;',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; export const get = () => wide;',
            },
          ],
        },
      ],
      name: 'an exported arrow narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export const slim: { a: number } = wide;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; export const slim = wide;',
            },
          ],
        },
      ],
      name: 'an exported variable narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const slim: { a: number } = wide;\nexport { slim };',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; const slim = wide;\nexport { slim };',
            },
          ],
        },
      ],
      name: 'a re-exported variable narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export function f(): { a: number } { return wide; }',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; export function f() { return wide; }',
            },
          ],
        },
      ],
      name: 'an exported function declaration narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export class C { m(): { a: number } { return wide; } }',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; export class C { m() { return wide; } }',
            },
          ],
        },
      ],
      name: 'a method of an exported class narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; class C { field: { a: number } = wide; }',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; class C { field = wide; }',
            },
          ],
        },
      ],
      name: 'a class field type that hides a member of its initializer is flagged',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; class C { readonly field: { a: number } = wide; }',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; class C { readonly field = wide; }',
            },
          ],
        },
      ],
      name: 'a readonly class field narrows just like a mutable one — the readonly fiction over a wider value is dropped',
      options: narrowingOnly,
    },
    {
      code: 'class C { seen: ReadonlySet<string> = new Set(["a"]); }',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [{ messageId: 'removeAnnotation', output: 'class C { seen = new Set(["a"]); }' }],
        },
      ],
      name: 'a class field typed as ReadonlySet over a fresh mutable Set is the same narrowing anti-pattern',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; export class C { field: { a: number } = wide; }',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { a: number; b: number }; export class C { field = wide; }',
            },
          ],
        },
      ],
      name: 'a field of an exported class narrows just like any other — a module boundary is no excuse',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { (x: number): void; extra: number }; const f: (x: number) => void = wide;',
      errors: [
        {
          messageId: 'narrowVarType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output: 'declare const wide: { (x: number): void; extra: number }; const f = wide;',
            },
          ],
        },
      ],
      name: 'a bare function-type annotation hides a property the callable value actually has',
      options: narrowingOnly,
    },
    {
      code: 'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = (): Fn => wide;',
      errors: [
        {
          messageId: 'narrowReturnType',
          suggestions: [
            {
              messageId: 'removeAnnotation',
              output:
                'type Fn = (x: number) => void; declare const wide: { (x: number): void; extra: number }; const get = () => wide;',
            },
          ],
        },
      ],
      name: 'a function-type return annotation hides a property of the returned callable value',
      options: narrowingOnly,
    },
  ],
  valid: [
    {
      code: 'declare const exact: { a: number; b: number }; const x: { a: number; b: number } = exact;',
      name: 'annotation matches the value exactly, so nothing is hidden',
      options: narrowingOnly,
    },
    {
      code: 'const x: number = 5;',
      name: 'widening a numeric literal to `number` hides no member',
      options: narrowingOnly,
    },
    {
      code: 'declare const lit: "a"; const x: string = lit;',
      name: 'widening a string literal to `string` hides no member',
      options: narrowingOnly,
    },
    {
      code: 'const x: unknown = { a: 1, b: 2 };',
      name: 'erasing to `unknown` is a deliberate generalization, not field hiding',
      options: narrowingOnly,
    },
    {
      code: 'declare const arr: number[]; const widened: (number | string)[] = arr;',
      name: 'widening an array element type hides no array member',
      options: narrowingOnly,
    },
    {
      code: 'declare const x: { a: number; b: number }; declare const y: { a: number; c: number }; const f = (cond: boolean): { a: number } => { if (cond) return x; return y; };',
      name: 'a member missing from some branch is not common to all returns, so it is not hidden',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const f = async (): Promise<{ a: number }> => wide;',
      name: 'an async function body type is the resolved value, not the Promise return type, so it is left alone',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const dict: { [k: string]: number } = wide;',
      name: 'an index-signature annotation is an open dictionary, not a fixed field subset',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; declare const slim: { a: number }; let x: { a: number } = wide; x = slim;',
      name: 'a reassigned `let` needs the wider annotation, so the workaround is impossible',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; const f = (n: number): { a: number } => n > 0 ? wide : f(n - 1);',
      name: 'a recursive arrow requires its return annotation, so it is left alone',
      options: narrowingOnly,
    },
    {
      code: 'const wrap = <T>(x: T): { value: T } => ({ value: x });',
      name: 'a generic return that references a type parameter is left alone',
      options: narrowingOnly,
    },
    {
      code: 'const p: { x: number } = { x: 1 };',
      name: 'an object literal that matches its annotation hides nothing',
      options: narrowingOnly,
    },
    {
      code: 'declare const exact: { a: number; b: number }; class C { field: { a: number; b: number } = exact; }',
      name: 'a class field annotation that matches its initializer exactly hides nothing',
      options: narrowingOnly,
    },
    {
      code: 'declare const wide: { a: number; b: number }; declare const slim: { a: number }; class C { field: { a: number } = wide; m() { this.field = slim; } }',
      name: 'a class field reassigned to a narrower value needs the wider annotation, so the workaround is impossible',
      options: narrowingOnly,
    },
    {
      code: 'class C { count: number = 5; }',
      name: 'widening a numeric literal field to `number` hides no member',
      options: narrowingOnly,
    },
    {
      code: 'type Ctx = { id: string }; type StrictCreate = (context: Ctx) => Record<string, () => void>; const create: StrictCreate = context => ({});',
      name: 'a function-type variable annotation over a plain function value hides nothing — the load-bearing form from create-rule.ts stays valid',
      options: narrowingOnly,
    },
    {
      code: 'declare const fn: (x: number) => void; const g: (x: number) => void = fn;',
      name: 'a function-type annotation matching a plain function value exactly hides nothing',
      options: narrowingOnly,
    },
  ],
});
