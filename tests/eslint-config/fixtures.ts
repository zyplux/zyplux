import type { LibraryFixtures } from '@zyplux/tests-fixtures';
import type { TestAPI } from 'vitest';

import { plugin, zyplux } from '@zyplux/eslint-config';
import { libraryTest } from '@zyplux/tests-fixtures';
import { ESLint, Linter } from 'eslint';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';
import * as z from 'zod';

const severityLevel = { error: 2, off: 0, warn: 1 } as const;
const SeveritySchema = z.union([z.literal(Object.values(severityLevel)), z.enum(['off', 'warn', 'error'])]);

const RuleEntrySchema = z.union([
  SeveritySchema,
  z.tuple([SeveritySchema]).rest(z.unknown()),
]) satisfies z.ZodType<Linter.RuleEntry>;

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

const storiesRootDir = fileURLToPath(new URL('./', import.meta.url));

type RuleLintOptions = { filename?: string; options?: unknown[] };

const pluginRuleConfig = (ruleName: string, options: undefined | unknown[]) => {
  const rules: Linter.RulesRecord = {
    [`@zyplux/${ruleName}`]: options === undefined ? ['error'] : ['error', ...options],
  };
  return {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        projectService: { allowDefaultProject: ['*.ts*', 'src/*.ts*'], defaultProject: 'tsconfig.json' },
        tsconfigRootDir: storiesRootDir,
      },
    },
    plugins: { '@zyplux': plugin },
    rules,
  };
};

export const applySuggestion = (code: string, { suggestions }: Linter.LintMessage, index = 0) => {
  const suggestion = suggestions?.[index];
  if (suggestion === undefined) throw new Error(`message has no suggestion at index ${index}`);
  const { range, text } = suggestion.fix;
  return code.slice(0, range[0]) + text + code.slice(range[1]);
};

type EslintFixtures = {
  fixRule: (code: string, lintOptions?: RuleLintOptions) => string;
  lint: (code: string) => Linter.LintMessage[];
  lintRule: (code: string, lintOptions?: RuleLintOptions) => Linter.LintMessage[];
  printedConfig: string;
  ruleId: string;
  ruleName: string;
};

export const test: TestAPI<EslintFixtures & LibraryFixtures> = libraryTest.extend<EslintFixtures>({
  fixRule: async ({ ruleName }, use) => {
    const linter = new Linter();
    await use(
      (code, { filename = 'file.ts', options } = {}) =>
        linter.verifyAndFix(code, pluginRuleConfig(ruleName, options), path.join(storiesRootDir, filename)).output,
    );
  },
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
  lintRule: async ({ ruleName }, use) => {
    const linter = new Linter();
    await use((code, { filename = 'file.ts', options } = {}) =>
      linter.verify(code, pluginRuleConfig(ruleName, options), path.join(storiesRootDir, filename)),
    );
  },
  printedConfig: [
    async ({}, use) => {
      await use(execFileSync('eslint', ['--print-config', 'src/index.ts'], { cwd: eslintConfigDir, encoding: 'utf8' }));
    },
    { scope: 'file' },
  ],
  ruleId: '',
  ruleName: '',
});

export { plugin, zyplux } from '@zyplux/eslint-config';
export { parseJson, readJsonSync } from '@zyplux/util';
export { describe, expect } from 'vitest';
