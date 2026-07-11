import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-zod-custom' });

type Case = [shape: string, code: string];

describe('12.1 flagging zod custom in every import shape', () => {
  test.for<Case>([
    [
      '1 flags z custom with a generic and a check function',
      ["import { z } from 'zod';", 'const schema = z.custom<string>(x => typeof x === "string");'].join('\n'),
    ],
    [
      '2 flags z custom called without arguments',
      ["import { z } from 'zod';", 'const schema = z.custom();'].join('\n'),
    ],
    [
      '3 flags an aliased import of zod, caught by type origin rather than the name z',
      ["import { z as zod } from 'zod';", 'const schema = zod.custom<{ id: string }>();'].join('\n'),
    ],
    [
      '4 flags a namespace import of zod',
      ["import * as zns from 'zod';", 'const schema = zns.custom(v => Boolean(v));'].join('\n'),
    ],
    [
      '5 flags z custom chained with parse',
      ["import { z } from 'zod';", 'const result = z.custom<{ id: string }>(v => Boolean(v)).parse(input);'].join('\n'),
    ],
  ])('12.1.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReport('noZodCustom');
  });
});

describe('12.2 permitting real zod combinators and non-zod custom', () => {
  test.for<Case>([
    [
      '1 allows the real zod object combinator',
      ["import { z } from 'zod';", 'const schema = z.object({ id: z.string() });'].join('\n'),
    ],
    ['2 allows the real zod string combinator', ["import { z } from 'zod';", 'const schema = z.string();'].join('\n')],
    [
      '3 allows the real zod discriminated union combinator',
      ["import { z } from 'zod';", 'const schema = z.discriminatedUnion("op", [a, b]);'].join('\n'),
    ],
    ['4 leaves a custom call not originating from zod alone', 'const schema = other.custom<string>(x => true);'],
    ['5 leaves a bare custom call alone', 'const schema = custom<string>(x => true);'],
  ])('12.2.%s', ([, code], { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});
