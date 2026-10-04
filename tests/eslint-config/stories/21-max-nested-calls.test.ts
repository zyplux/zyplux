import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'max-nested-calls' });

type Case = [description: string, code: string];

const ordinaryCases: Case[] = [
  ['ordinary calls', 'declare function call(v?: unknown): unknown; call(call(call(call())));'],
  ['constructors', 'declare class Box { constructor(v?: unknown); } new Box(new Box(new Box(new Box())));'],
  [
    'calls inside object arguments',
    'declare function call(v?: unknown): unknown; call({ v: call({ v: call({ v: call() }) }) });',
  ],
  ['a method named like Zod', 'const z = { object: (v?: unknown) => v }; z.object(z.object(z.object(z.object())));'],
  [
    'a schema-or-string return type',
    'import * as z from "zod"; declare function call(v?: unknown): z.ZodString | string; call(call(call(call())));',
  ],
  ['any return types', 'declare function call(v?: any): any; call(call(call(call())));'],
];

const boundaryCases: Case[] = [
  ['arrow callback', 'call(call(call(() => call())));'],
  ['function callback', 'call(call(call(function run() { return call(); })));'],
  ['class expression', 'call(call(call(class Box { field = call(); })));'],
  ['static block', 'call(call(call(class Box { static { call(); } })));'],
  ['JSX element', 'call(call(call(<div>{call()}</div>)));'],
  ['JSX fragment', 'call(call(call(<>{call()}</>)));'],
];

describe('21.1 preserving the call depth limit', () => {
  test.for(ordinaryCases)('21.1.1 rejects excessive nesting for %s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('max-nested-calls');
  });

  test('21.1.2 accepts calls at the default limit', ({ lintRule }) => {
    expect(lintRule('declare function call(v?: unknown): unknown; call(call(call()));')).toReportNothing();
  });

  test('21.1.3 honors the configured limit', ({ lintRule }) => {
    const code = 'declare function call(v?: unknown): unknown; call(call(call()));';
    expect(lintRule(code, { options: [{ max: 2 }] })).toReport('max-nested-calls');
    expect(lintRule(code, { options: [{ max: 3 }] })).toReportNothing();
  });

  test.for(boundaryCases)('21.1.4 resets depth at a %s', ([, code], { lintRule }) => {
    expect(
      lintRule(`declare function call(v?: unknown): unknown; ${code}`, { filename: 'file.tsx' }),
    ).toReportNothing();
  });

  test('21.1.5 does not count fluent receiver calls as nested arguments', ({ lintRule }) => {
    expect(
      lintRule('declare const chain: { next(): typeof chain }; chain.next().next().next().next().next();'),
    ).toReportNothing();
  });
});

describe('21.2 exempting schema construction precisely', () => {
  test('21.2.1 accepts deeply nested object and array schemas', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; const Schema = z.object({ reviews: z.array(z.object({ user: z.object({ login: z.string() }).nullable() })) });',
      ),
    ).toReportNothing();
  });

  test('21.2.2 recognizes aliased imports and factories returning schemas', ({ lintRule }) => {
    expect(
      lintRule(
        'import { z as validator } from "zod"; const makeSchema = () => validator.string(); const Schema = validator.object({ a: validator.object({ b: validator.object({ c: validator.object({ d: makeSchema() }) }) }) });',
      ),
    ).toReportNothing();
  });

  test('21.2.3 recognizes unions consisting entirely of schemas', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; declare function makeSchema(v?: unknown): z.ZodString | z.ZodNumber; makeSchema(makeSchema(makeSchema(makeSchema(makeSchema()))));',
      ),
    ).toReportNothing();
  });

  test('21.2.4 still checks ordinary calls inside schema arguments', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; declare function readDefault(): string; const Schema = z.object({ a: z.object({ b: z.object({ c: z.object({ d: z.string().default(readDefault()) }) }) }) });',
      ),
    ).toReport('max-nested-calls');
  });

  test('21.2.5 still checks computation inside schema callbacks', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; declare function call(v?: unknown): string; const Schema = z.string().transform(v => call(call(call(call(v)))));',
      ),
    ).toReport('max-nested-calls');
  });

  test('21.2.6 replaces Unicorn only for TypeScript files', ({ zyplux }) => {
    const configs = zyplux();
    const replacement = configs.find(config => config.rules?.['@zyplux/max-nested-calls'] !== undefined);
    expect(replacement).toMatchObject({
      files: ['**/*.{ts,tsx}'],
      rules: { '@zyplux/max-nested-calls': 'error', 'unicorn/max-nested-calls': 'off' },
    });
    expect(
      configs.some(
        config =>
          config.rules?.['unicorn/max-nested-calls'] !== 'off' &&
          config.rules?.['unicorn/max-nested-calls'] !== undefined,
      ),
    ).toBe(true);
  });
});

describe('21.3 sharing schema collection detection', () => {
  test('21.3.1 exempts nested calls returning plain schema collections', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; declare function build(v?: unknown): { group: { text: z.ZodString } }; build(build(build(build())));',
      ),
    ).toReportNothing();
  });

  test('21.3.2 keeps the nesting limit for mixed objects', ({ lintRule }) => {
    expect(
      lintRule(
        'import * as z from "zod"; declare function build(v?: unknown): { text: z.ZodString; retries: number }; build(build(build(build())));',
      ),
    ).toReport('max-nested-calls');
  });
});
