import type { Linter } from 'eslint';

import * as z from 'zod';

const severityLevel = { error: 2, off: 0, warn: 1 } as const;
const SeveritySchema = z.union([z.literal(Object.values(severityLevel)), z.enum(['off', 'warn', 'error'])]);

const RuleEntrySchema = z.union([
  SeveritySchema,
  z.tuple([SeveritySchema]).rest(z.unknown()),
]) satisfies z.ZodType<Linter.RuleEntry>;

export const ResolvedConfigSchema = z.object({ rules: z.record(z.string(), RuleEntrySchema) });

export const ParserOptionsSchema = z.looseObject({ tsconfigRootDir: z.string() });

export const PrintedConfigSchema = z.looseObject({
  languageOptions: z.looseObject({ parserOptions: ParserOptionsSchema }),
});

export type PrintedConfig = z.infer<typeof PrintedConfigSchema>;
