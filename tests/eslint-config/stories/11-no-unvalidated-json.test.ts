import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-unvalidated-json' });

type Case = [shape: string, code: string];

describe('11.1 flagging JSON reads that bypass schema validation', () => {
  test('11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message', ({ lintRule }) => {
    const messages = lintRule('const parsed = JSON.parse(text);');
    expect(messages).toReport('validateJson');
    expect(messages[0]?.message).toContain('JSON.parse(…)');
  });

  test('11.1.2 flags an awaited json call returning an any promise, naming the api in the message', ({
    lintRule,
  }) => {
    const code = ['declare const response: { json(): Promise<any> };', 'const body = await response.json();'].join(
      '\n',
    );
    const messages = lintRule(code);
    expect(messages).toReport('validateJson');
    expect(messages[0]?.message).toContain('….json()');
  });

  test.for<Case>([
    ['11.1.3 flags a JSON parse annotated unknown', 'const parsed: unknown = JSON.parse(text);'],
    ['11.1.4 flags a JSON parse read off before validation', 'const version = JSON.parse(text).version;'],
    ['11.1.5 flags a JSON parse passed to a non-zod consumer', 'normalizeRules(JSON.parse(printed));'],
    [
      '11.1.6 flags a non-awaited any promise json call, caught by type rather than syntax',
      ['declare const response: { json(): Promise<any> };', 'const pending = response.json();'].join('\n'),
    ],
    [
      '11.1.7 flags a synchronous json call returning any',
      ['declare const reader: { json(): any };', 'const data = reader.json().version;'].join('\n'),
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('validateJson');
  });
});

describe('11.2 permitting validated reads and non-boundary json calls', () => {
  test.for<Case>([
    ['11.2.1 allows a JSON parse flowing into schema parse', 'const parsed = Schema.parse(JSON.parse(text));'],
    [
      '11.2.2 allows a JSON parse flowing into schema safe parse',
      'const parsed = Schema.safeParse(JSON.parse(text));',
    ],
    [
      '11.2.3 allows an awaited json call flowing into schema parse',
      [
        'declare const response: { json(): Promise<any> };',
        'const body = Schema.parse(await response.json());',
      ].join('\n'),
    ],
    [
      '11.2.4 allows an awaited json call flowing into schema parse async',
      [
        'declare const response: { json(): Promise<any> };',
        'const body = await Schema.parseAsync(await response.json());',
      ].join('\n'),
    ],
    ['11.2.5 leaves JSON stringify alone, which is not a parse boundary', 'const text = JSON.stringify(value);'],
    [
      '11.2.6 leaves a json call returning a concrete type alone',
      [
        'type Config = { id: string };',
        'declare const client: { json(): Promise<Config> };',
        'const cfg = await client.json();',
      ].join('\n'),
    ],
    [
      '11.2.7 leaves a json call with a concrete return type built from an argument alone',
      [
        'declare const builder: { json(body: unknown): { ok: boolean } };',
        'const sent = builder.json({ ok: true });',
      ].join('\n'),
    ],
  ])('%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});
