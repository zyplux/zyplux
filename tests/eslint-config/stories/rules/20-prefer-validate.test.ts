import { describe, expect, test } from './rules.ts';

test.override({ ruleName: 'prefer-validate' });

describe('20.1 choosing boolean validation for success-only parsing', () => {
  test.for([
    "import * as z from 'zod'; const Schema = z.string(); const ok = Schema.safeParse(input).success;",
    "import { PackageJsonSchema } from '@zyplux/util/contracts'; const ok = !PackageJsonSchema.safeParse(input).success;",
    "import type * as z from 'zod'; const check = (schema: z.ZodType, input: unknown) => schema.safeParse(input).success;",
    "import * as z from 'zod'; const { success: ok } = z.string().safeParse(input);",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input); if (parsed.success) accept();",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input); const ok = !parsed.success; if (parsed.success) accept();",
    "import * as z from 'zod'; const Schema = z.string(); const ok = z.safeParse(Schema, input).success;",
    "import { safeParse as parse, string } from 'zod'; const ok = parse(string(), input).success;",
  ])('20.1.1 reports success-only parsing: %s', (code, { lintRule }) => {
    expect(lintRule(code)).toReport('preferValidate');
  });

  test.for([
    "import * as z from 'zod'; const Schema = z.string(); const ok = (await Schema.safeParseAsync(input)).success;",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = await Schema.spa(input); if (parsed.success) accept();",
    "import * as z from 'zod'; const Schema = z.string(); const { success } = await z.safeParseAsync(Schema, input);",
  ])('20.1.2 recommends asynchronous validation: %s', (code, { lintRule }) => {
    const reports = lintRule(code);
    expect(reports).toReport('preferValidate');
    expect(reports[0]?.message).toContain('validateAsync()');
  });
});

describe('20.2 retaining parsed data, errors and throwing assertions', () => {
  test.for([
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input); if (parsed.success) accept(parsed.data);",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input); if (!parsed.success) report(parsed.error);",
    "import * as z from 'zod'; const Schema = z.string(); const { success, data } = Schema.safeParse(input);",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input); forward(parsed);",
    "import * as z from 'zod'; const Schema = z.string(); export const parsed = Schema.safeParse(input); if (parsed.success) accept();",
    "import * as z from 'zod'; const Schema = z.string(); let parsed = Schema.safeParse(input); parsed = Schema.safeParse(other); if (parsed.success) accept();",
    "import * as z from 'zod'; const Schema = z.string(); const parsed = Schema.safeParse(input);",
    "import * as z from 'zod'; const Schema = z.string(); Schema.parse(input);",
    "import * as z from 'zod'; const Schema = z.string(); const ok = Schema.validate(input);",
    "import * as z from 'zod'; const Schema = z.string(); const { success = true } = Schema.safeParse(input);",
    "import * as z from 'zod'; const Schema = z.string(); Schema.safeParseAsync(input).then(parsed => parsed.success);",
    "import * as z from 'zod/v3'; const Schema = z.string(); const ok = Schema.safeParse(input).success;",
    'const other = { safeParse: () => ({ success: true }) }; const ok = other.safeParse().success;',
  ])('20.2.1 leaves parsing semantics intact: %s', (code, { lintRule }) => {
    expect(lintRule(code)).toReportNothing();
  });
});
