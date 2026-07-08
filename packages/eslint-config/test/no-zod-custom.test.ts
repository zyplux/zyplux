import { noZodCustom } from '#rules/no-zod-custom';

import { typeAwareRuleTester } from './rule-tester';

typeAwareRuleTester.run('no-zod-custom', noZodCustom, {
  invalid: [
    {
      code: ["import { z } from 'zod';", 'const schema = z.custom<string>(x => typeof x === "string");'].join('\n'),
      errors: [{ messageId: 'noZodCustom' }],
      name: 'z.custom with generic and check',
    },
    {
      code: ["import { z } from 'zod';", 'const schema = z.custom();'].join('\n'),
      errors: [{ messageId: 'noZodCustom' }],
      name: 'z.custom without arguments',
    },
    {
      code: ["import { z as zod } from 'zod';", 'const schema = zod.custom<{ id: string }>();'].join('\n'),
      errors: [{ messageId: 'noZodCustom' }],
      name: 'aliased zod import — caught by type origin, not the name `z`',
    },
    {
      code: ["import * as zns from 'zod';", 'const schema = zns.custom(v => Boolean(v));'].join('\n'),
      errors: [{ messageId: 'noZodCustom' }],
      name: 'namespace import of zod',
    },
    {
      code: ["import { z } from 'zod';", 'const result = z.custom<{ id: string }>(v => Boolean(v)).parse(input);'].join(
        '\n',
      ),
      errors: [{ messageId: 'noZodCustom' }],
      name: 'z.custom chained with .parse',
    },
  ],
  valid: [
    ["import { z } from 'zod';", 'const schema = z.object({ id: z.string() });'].join('\n'),
    ["import { z } from 'zod';", 'const schema = z.string();'].join('\n'),
    {
      code: ["import { z } from 'zod';", 'const schema = z.discriminatedUnion("op", [a, b]);'].join('\n'),
      name: 'discriminatedUnion is not custom',
    },
    {
      code: 'const schema = other.custom<string>(x => true);',
      name: 'custom on a non-zod receiver is not flagged (type origin check)',
    },
    {
      code: 'const schema = custom<string>(x => true);',
      name: 'unqualified custom not from zod is not flagged',
    },
  ],
});
