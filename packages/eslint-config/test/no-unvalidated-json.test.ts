import { noUnvalidatedJson } from '#rules/no-unvalidated-json';

import { typeAwareRuleTester } from './rule-tester';

typeAwareRuleTester.run('no-unvalidated-json', noUnvalidatedJson, {
  invalid: [
    {
      code: 'const parsed = JSON.parse(text);',
      errors: [{ data: { api: 'JSON.parse(…)' }, messageId: 'validateJson' }],
      name: 'bare JSON.parse assigned to a variable',
    },
    {
      code: 'const parsed: unknown = JSON.parse(text);',
      errors: [{ messageId: 'validateJson' }],
      name: 'JSON.parse annotated `: unknown`',
    },
    {
      code: 'const version = JSON.parse(text).version;',
      errors: [{ messageId: 'validateJson' }],
      name: 'member access straight off JSON.parse',
    },
    {
      code: 'normalizeRules(JSON.parse(printed));',
      errors: [{ messageId: 'validateJson' }],
      name: 'JSON.parse passed to a non-zod consumer',
    },
    {
      code: ['declare const response: { json(): Promise<any> };', 'const body = await response.json();'].join('\n'),
      errors: [{ data: { api: '….json()' }, messageId: 'validateJson' }],
      name: 'awaited .json() returning Promise<any>',
    },
    {
      code: ['declare const response: { json(): Promise<any> };', 'const pending = response.json();'].join('\n'),
      errors: [{ messageId: 'validateJson' }],
      name: 'non-awaited Promise<any> .json() — caught by type, missed by the old syntactic rule',
    },
    {
      code: ['declare const reader: { json(): any };', 'const data = reader.json().version;'].join('\n'),
      errors: [{ messageId: 'validateJson' }],
      name: 'synchronous .json() returning any',
    },
  ],
  valid: [
    {
      code: 'const parsed = Schema.parse(JSON.parse(text));',
      name: 'JSON.parse flows directly into schema.parse',
    },
    {
      code: 'const parsed = Schema.safeParse(JSON.parse(text));',
      name: 'JSON.parse flows directly into schema.safeParse',
    },
    {
      code: ['declare const response: { json(): Promise<any> };', 'const body = Schema.parse(await response.json());'].join('\n'),
      name: 'awaited .json() flows directly into schema.parse',
    },
    {
      code: ['declare const response: { json(): Promise<any> };', 'const body = await Schema.parseAsync(await response.json());'].join('\n'),
      name: 'awaited .json() flows into schema.parseAsync',
    },
    {
      code: 'const text = JSON.stringify(value);',
      name: 'JSON.stringify is not a parse boundary',
    },
    {
      code: ['type Config = { id: string };', 'declare const client: { json(): Promise<Config> };', 'const cfg = await client.json();'].join('\n'),
      name: 'a domain .json() returning a typed value is left alone',
    },
    {
      code: ['declare const builder: { json(body: unknown): { ok: boolean } };', 'const sent = builder.json({ ok: true });'].join('\n'),
      name: 'a .json() returning a concrete type (response builder) is not a read boundary',
    },
  ],
});
