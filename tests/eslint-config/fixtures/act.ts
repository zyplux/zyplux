import { plugin, zyplux } from '@zyplux/eslint-config';
import { PrintedConfigSchema, ResolvedConfigSchema } from '@zyplux/eslint-config/contracts';
import { parseJson, readJsonSync } from '@zyplux/util';
import { ESLint, Linter } from 'eslint';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';

export const subjects: { plugin: typeof plugin; zyplux: typeof zyplux } = { plugin, zyplux };

export type ZypluxConfig = ReturnType<typeof zyplux>;

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

const eslintConfigDir = fileURLToPath(new URL('../../../packages/eslint-config/', import.meta.url));

const suiteDir = fileURLToPath(new URL('../', import.meta.url));

export type RuleLintOptions = { filename?: string; options?: unknown[] };

export type RuleLintWithOptions = (code: string, lintOptions?: RuleLintOptions) => Linter.LintMessage[];
type RuleLint = (code: string) => Linter.LintMessage[];

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
        tsconfigRootDir: suiteDir,
      },
    },
    plugins: { '@zyplux': plugin },
    rules,
  };
};

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

export const printConfig = () =>
  execFileSync('eslint', ['--print-config', 'src/index.ts'], { cwd: eslintConfigDir, encoding: 'utf8' });

export const parsePrintedConfig = (printedConfig: string) => parseJson(printedConfig, PrintedConfigSchema);

const rulesSnapshotUrl = new URL('../../../packages/eslint-config/rules.json', import.meta.url);

export const loadRulesSnapshot = () => readJsonSync(rulesSnapshotUrl, PrintedConfigSchema);

export type { PrintedConfig } from '@zyplux/eslint-config/contracts';
