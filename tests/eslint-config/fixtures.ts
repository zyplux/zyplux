import type { LibraryFixtures } from '@zyplux/tests-fixtures';
import type { TestAPI } from 'vitest';

import { zyplux } from '@zyplux/eslint-config';
import { libraryTest } from '@zyplux/tests-fixtures';
import { ESLint, Linter } from 'eslint';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';
import * as z from 'zod';

const severityLevel = { error: 2, off: 0, warn: 1 } as const;
const SeveritySchema = z.union([z.literal(Object.values(severityLevel)), z.enum(['off', 'warn', 'error'])]);

const RuleEntrySchema = z.union([SeveritySchema, z.tuple([SeveritySchema]).rest(z.unknown())]) satisfies z.ZodType<Linter.RuleEntry>;

const ResolvedConfigSchema = z.object({ rules: z.record(z.string(), RuleEntrySchema) });

const resolveMergedRule = async (ruleId: string) => {
  const eslint = new ESLint({ overrideConfig: zyplux(), overrideConfigFile: true });
  const resolved: unknown = await eslint.calculateConfigForFile('example.ts');
  return ResolvedConfigSchema.parse(resolved).rules[ruleId] ?? 'off';
};

const mergedRuleCache = new Map<string, Promise<Linter.RuleEntry>>();

const getMergedRule = (ruleId: string) => {
  const cached = mergedRuleCache.get(ruleId);
  if (cached !== undefined) return cached;
  const pending = resolveMergedRule(ruleId);
  mergedRuleCache.set(ruleId, pending);
  return pending;
};

const eslintConfigDir = fileURLToPath(new URL('../../packages/eslint-config/', import.meta.url));

type EslintFixtures = {
  lint: (code: string) => Linter.LintMessage[];
  printedConfig: string;
  ruleId: string;
};

export const test: TestAPI<EslintFixtures & LibraryFixtures> = libraryTest.extend<EslintFixtures>({
  lint: async ({ ruleId }, use) => {
    const mergedRule = await getMergedRule(ruleId);
    const linter = new Linter();
    await use(code =>
      linter.verify(code, {
        languageOptions: { parser: tseslint.parser },
        plugins: { '@typescript-eslint': tseslint.plugin },
        rules: { [ruleId]: mergedRule },
      }),
    );
  },
  printedConfig: [
    async ({}, use) => {
      await use(execFileSync('eslint', ['--print-config', 'src/index.ts'], { cwd: eslintConfigDir, encoding: 'utf8' }));
    },
    { scope: 'file' },
  ],
  ruleId: '',
});

export { plugin, zyplux } from '@zyplux/eslint-config';
export { parseJson, readJsonSync } from '@zyplux/util';
export { describe, expect } from 'vitest';
