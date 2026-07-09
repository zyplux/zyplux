import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'no-zod-custom' });

const customReport = [{ messageId: 'noZodCustom' }];

describe('12.1 flagging zod custom in every import shape', () => {
  test('12.1.1 flags z custom with a generic and check, and without arguments', ({ lintRule }) => {
    expect(
      lintRule(["import { z } from 'zod';", 'const schema = z.custom<string>(x => typeof x === "string");'].join('\n')),
    ).toMatchObject(customReport);
    expect(lintRule(["import { z } from 'zod';", 'const schema = z.custom();'].join('\n'))).toMatchObject(customReport);
  });

  test('12.1.2 flags aliased and namespace imports of zod, caught by type origin rather than the name z', ({
    lintRule,
  }) => {
    expect(
      lintRule(["import { z as zod } from 'zod';", 'const schema = zod.custom<{ id: string }>();'].join('\n')),
    ).toMatchObject(customReport);
    expect(
      lintRule(["import * as zns from 'zod';", 'const schema = zns.custom(v => Boolean(v));'].join('\n')),
    ).toMatchObject(customReport);
  });

  test('12.1.3 flags z custom chained with parse', ({ lintRule }) => {
    expect(
      lintRule(
        ["import { z } from 'zod';", 'const result = z.custom<{ id: string }>(v => Boolean(v)).parse(input);'].join(
          '\n',
        ),
      ),
    ).toMatchObject(customReport);
  });
});

describe('12.2 permitting real zod combinators and non-zod custom', () => {
  test('12.2.1 allows real zod combinators such as object, string, and discriminated union', ({ lintRule }) => {
    expect(
      lintRule(["import { z } from 'zod';", 'const schema = z.object({ id: z.string() });'].join('\n')),
    ).toHaveLength(0);
    expect(lintRule(["import { z } from 'zod';", 'const schema = z.string();'].join('\n'))).toHaveLength(0);
    expect(
      lintRule(["import { z } from 'zod';", 'const schema = z.discriminatedUnion("op", [a, b]);'].join('\n')),
    ).toHaveLength(0);
  });

  test('12.2.2 leaves custom calls that do not originate from zod alone', ({ lintRule }) => {
    expect(lintRule('const schema = other.custom<string>(x => true);')).toHaveLength(0);
    expect(lintRule('const schema = custom<string>(x => true);')).toHaveLength(0);
  });
});
