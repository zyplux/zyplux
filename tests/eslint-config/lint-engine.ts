import { plugin, zyplux } from '@zyplux/eslint-config';
import { ESLint, Linter } from 'eslint';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';

import { ResolvedConfigSchema } from './contracts.ts';

const suiteDir = fileURLToPath(new URL('./', import.meta.url));
export type RuleLintOptions = { filename?: string; options?: unknown[] };

const pluginRuleConfig = (ruleName: string, options: undefined | unknown[]) => {
  const docs = plugin.rules?.[ruleName]?.meta?.docs;
  const isTypeAware = docs !== undefined && 'requiresTypeChecking' in docs && docs.requiresTypeChecking === true;
  const rules: Linter.RulesRecord = {
    [`@zyplux/${ruleName}`]: options === undefined ? ['error'] : ['error', ...options],
  };
  return {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ...(isTypeAware && {
          projectService: { allowDefaultProject: ['*.ts*', 'src/*.ts*'], defaultProject: 'tsconfig.json' },
          tsconfigRootDir: suiteDir,
        }),
      },
    },
    plugins: { '@zyplux': plugin },
    rules,
  };
};

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

export type RuleLintWithOptions = (code: string, lintOptions?: RuleLintOptions) => Linter.LintMessage[];
type RuleLint = (code: string) => Linter.LintMessage[];

export const createFixRule = (ruleName: string) => {
  const linter = new Linter();
  return (code: string, { filename = 'file.ts', options }: RuleLintOptions = {}) =>
    linter.verifyAndFix(code, pluginRuleConfig(ruleName, options), path.join(suiteDir, filename)).output;
};

export const createMergedLint = async (ruleId: string): Promise<RuleLint> => {
  const mergedRule = await getMergedRule(ruleId);
  const linter = new Linter();
  return (code: string) =>
    linter.verify(code, {
      languageOptions: { parser: tseslint.parser },
      plugins: { '@typescript-eslint': tseslint.plugin },
      rules: { [ruleId]: mergedRule },
    });
};

export const createLintRule = (ruleName: string): RuleLintWithOptions => {
  const linter = new Linter();
  return (code, { filename = 'file.ts', options }: RuleLintOptions = {}) =>
    linter.verify(code, pluginRuleConfig(ruleName, options), path.join(suiteDir, filename));
};
