import { describe, expect, test } from './rules.ts';

test.override({ ruleName: 'no-unvalidated-json' });

const schemaImport = "import * as z from 'zod'; const Schema = z.string();";

type Case = [shape: string, code: string];

describe('11.1 flagging JSON reads that bypass schema validation', () => {
  test('11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message', ({ lintRule }) => {
    const messages = lintRule('const parsed = JSON.parse(text);');
    expect(messages).toReport('validateJson');
    expect(messages[0]?.message).toContain('JSON.parse(…)');
  });

  test('11.1.2 flags an awaited json call returning an any promise, naming the api in the message', ({ lintRule }) => {
    const code = ['declare const response: { json(): Promise<any> };', 'const body = await response.json();'].join(
      '\n',
    );
    const messages = lintRule(code);
    expect(messages).toReport('validateJson');
    expect(messages[0]?.message).toContain('….json()');
  });

  test.for<Case>([
    ['3 flags a JSON parse annotated unknown', 'const parsed: unknown = JSON.parse(text);'],
    ['4 flags a JSON parse read off before validation', 'const version = JSON.parse(text).version;'],
    [
      '8 flags JSON passed to an unrelated validator',
      'const form = { validate: (input: unknown) => true }; form.validate(JSON.parse(text));',
    ],
    [
      '9 flags JSON passed to an unrelated async validator',
      'const form = { validateAsync: async (input: unknown) => true }; await form.validateAsync(JSON.parse(text));',
    ],
    [
      '10 flags JSON passed to an unrelated parser',
      'const parser = { parse: (input: unknown) => input }; parser.parse(JSON.parse(text));',
    ],
    [
      '11 flags a JSON promise passed into validation',
      `${schemaImport} declare const response: { json(): Promise<any> }; Schema.validateAsync(response.json());`,
    ],
    [
      '12 flags a JSON promise passed into parsing',
      `${schemaImport} declare const response: { json(): Promise<any> }; Schema.parse(response.json());`,
    ],
    [
      '13 flags a JSON promise passed into functional validation',
      `${schemaImport} declare const response: { json(): Promise<any> }; z.validateAsync(Schema, response.json());`,
    ],
    ['14 flags JSON used as validation options', `${schemaImport} Schema.validate('name', JSON.parse(text));`],
    ['15 flags a functional validator without a schema', `${schemaImport} z.validate({}, JSON.parse(text));`],
    ['5 flags a JSON parse passed to a non-zod consumer', 'normalizeRules(JSON.parse(printed));'],
    [
      '6 flags a non-awaited any promise json call, caught by type rather than syntax',
      ['declare const response: { json(): Promise<any> };', 'const pending = response.json();'].join('\n'),
    ],
    [
      '7 flags a synchronous json call returning any',
      ['declare const reader: { json(): any };', 'const data = reader.json().version;'].join('\n'),
    ],
  ])('11.1.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('validateJson');
  });
});

describe('11.2 permitting validated reads and non-boundary json calls', () => {
  test.for<Case>([
    ['1 allows a JSON parse flowing into schema parse', 'const parsed = Schema.parse(JSON.parse(text));'],
    ['2 allows a JSON parse flowing into schema safe parse', 'const parsed = Schema.safeParse(JSON.parse(text));'],
    [
      '3 allows an awaited json call flowing into schema parse',
      ['declare const response: { json(): Promise<any> };', 'const body = Schema.parse(await response.json());'].join(
        '\n',
      ),
    ],
    [
      '4 allows an awaited json call flowing into schema parse async',
      [
        'declare const response: { json(): Promise<any> };',
        'const body = await Schema.parseAsync(await response.json());',
      ].join('\n'),
    ],
    ['5 leaves JSON stringify alone, which is not a parse boundary', 'const text = JSON.stringify(value);'],
    [
      '6 leaves a json call returning a concrete type alone',
      [
        'type Config = { id: string };',
        'declare const client: { json(): Promise<Config> };',
        'const cfg = await client.json();',
      ].join('\n'),
    ],
    [
      '7 leaves a json call with a concrete return type built from an argument alone',
      [
        'declare const builder: { json(body: unknown): { ok: boolean } };',
        'const sent = builder.json({ ok: true });',
      ].join('\n'),
    ],
    ['10 allows namespace boolean validation', 'const valid = z.validate(Schema, JSON.parse(text));'],
    [
      '11 allows imported boolean validation',
      "import { validate as check } from 'zod'; const valid = check(Schema, JSON.parse(text));",
    ],
    ['12 allows functional parsing', 'const parsed = z.parse(Schema, JSON.parse(text));'],
    [
      '13 allows namespace async validation of resolved JSON',
      'declare const response: { json(): Promise<any> }; const valid = await z.validateAsync(Schema, await response.json());',
    ],
    [
      '14 allows imported async validation of resolved JSON',
      "import { validateAsync as check } from 'zod'; declare const response: { json(): Promise<any> }; const valid = await check(Schema, await response.json());",
    ],
    [
      '15 allows instance async validation of resolved JSON',
      'declare const response: { json(): Promise<any> }; const valid = await Schema.validateAsync(await response.json());',
    ],
    ['8 allows JSON flowing into boolean validation', 'const valid = Schema.validate(JSON.parse(text));'],
    [
      '9 allows JSON flowing into asynchronous boolean validation',
      'const valid = await Schema.validateAsync(JSON.parse(text));',
    ],
  ])('11.2.%s', ([, code], { lintRule }) => {
    expect(lintRule(`${schemaImport} ${code}`)).toReportNothing();
  });
});
