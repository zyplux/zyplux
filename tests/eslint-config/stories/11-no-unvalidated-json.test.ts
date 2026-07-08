import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-unvalidated-json' });

const validateReport = [{ messageId: 'validateJson' }];

describe('11.1 flagging JSON reads that bypass schema validation', () => {
  test('11.1.1 flags a bare JSON parse assigned to a variable, naming the api in the message', ({ lintRule }) => {
    const messages = lintRule('const parsed = JSON.parse(text);');
    expect(messages).toMatchObject(validateReport);
    expect(messages[0]?.message).toContain('JSON.parse(…)');
  });

  test('11.1.2 flags a JSON parse annotated unknown, read off, or passed to a non-zod consumer', ({ lintRule }) => {
    expect(lintRule('const parsed: unknown = JSON.parse(text);')).toMatchObject(validateReport);
    expect(lintRule('const version = JSON.parse(text).version;')).toMatchObject(validateReport);
    expect(lintRule('normalizeRules(JSON.parse(printed));')).toMatchObject(validateReport);
  });

  test('11.1.3 flags an awaited json call returning an any promise, naming the api in the message', ({ lintRule }) => {
    const code = ['declare const response: { json(): Promise<any> };', 'const body = await response.json();'].join(
      '\n',
    );
    const messages = lintRule(code);
    expect(messages).toMatchObject(validateReport);
    expect(messages[0]?.message).toContain('….json()');
  });

  test('11.1.4 flags a non-awaited any promise json call, caught by type rather than syntax', ({ lintRule }) => {
    expect(
      lintRule(['declare const response: { json(): Promise<any> };', 'const pending = response.json();'].join('\n')),
    ).toMatchObject(validateReport);
  });

  test('11.1.5 flags a synchronous json call returning any', ({ lintRule }) => {
    expect(
      lintRule(['declare const reader: { json(): any };', 'const data = reader.json().version;'].join('\n')),
    ).toMatchObject(validateReport);
  });
});

describe('11.2 permitting validated reads and non-boundary json calls', () => {
  test('11.2.1 allows a JSON parse flowing directly into schema parse or safe parse', ({ lintRule }) => {
    expect(lintRule('const parsed = Schema.parse(JSON.parse(text));')).toHaveLength(0);
    expect(lintRule('const parsed = Schema.safeParse(JSON.parse(text));')).toHaveLength(0);
  });

  test('11.2.2 allows an awaited json call flowing into schema parse or parse async', ({ lintRule }) => {
    expect(
      lintRule(
        ['declare const response: { json(): Promise<any> };', 'const body = Schema.parse(await response.json());'].join(
          '\n',
        ),
      ),
    ).toHaveLength(0);
    expect(
      lintRule(
        [
          'declare const response: { json(): Promise<any> };',
          'const body = await Schema.parseAsync(await response.json());',
        ].join('\n'),
      ),
    ).toHaveLength(0);
  });

  test('11.2.3 leaves JSON stringify alone, which is not a parse boundary', ({ lintRule }) => {
    expect(lintRule('const text = JSON.stringify(value);')).toHaveLength(0);
  });

  test('11.2.4 leaves json calls returning concrete types alone', ({ lintRule }) => {
    expect(
      lintRule(
        [
          'type Config = { id: string };',
          'declare const client: { json(): Promise<Config> };',
          'const cfg = await client.json();',
        ].join('\n'),
      ),
    ).toHaveLength(0);
    expect(
      lintRule(
        [
          'declare const builder: { json(body: unknown): { ok: boolean } };',
          'const sent = builder.json({ ok: true });',
        ].join('\n'),
      ),
    ).toHaveLength(0);
  });
});
