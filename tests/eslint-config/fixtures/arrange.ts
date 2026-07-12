import { plugin, zyplux } from '@zyplux/eslint-config';
import { PrintedConfigSchema } from '@zyplux/eslint-config/contracts';
import { readJsonSync } from '@zyplux/util';
import { Linter } from 'eslint';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tseslint from 'typescript-eslint';

export const suiteDir = fileURLToPath(new URL('../', import.meta.url));

export const eslintConfigDir = fileURLToPath(new URL('../../../packages/eslint-config/', import.meta.url));

export type RuleLintOptions = { filename?: string; options?: unknown[] };

export const pluginRuleConfig = (ruleName: string, options: undefined | unknown[]): Linter.Config => {
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

const PACKAGE_SOURCE_TSCONFIG = JSON.stringify({
  compilerOptions: {
    isolatedModules: true,
    module: 'Preserve',
    moduleDetection: 'force',
    moduleResolution: 'bundler',
    skipLibCheck: true,
    strict: true,
    target: 'ESNext',
    types: [],
    verbatimModuleSyntax: true,
  },
  include: ['.'],
});

export const writePackageSource = (
  packageSource: Record<string, string>,
): { cleanup: () => void; tsconfigRootDir: string } => {
  const tsconfigRootDir = mkdtempSync(path.join(os.tmpdir(), 'zyplux-package-source-'));
  writeFileSync(path.join(tsconfigRootDir, 'tsconfig.json'), PACKAGE_SOURCE_TSCONFIG);
  for (const [filename, code] of Object.entries(packageSource)) {
    writeFileSync(path.join(tsconfigRootDir, filename), code);
  }
  return {
    cleanup: () => {
      rmSync(tsconfigRootDir, { force: true, recursive: true });
    },
    tsconfigRootDir,
  };
};

const rulesSnapshotUrl = new URL('../../../packages/eslint-config/rules.json', import.meta.url);

export const loadRulesSnapshot = () => readJsonSync(rulesSnapshotUrl, PrintedConfigSchema);

export type ZypluxConfig = ReturnType<typeof zyplux>;

export const subjects: { plugin: typeof plugin; zyplux: typeof zyplux } = { plugin, zyplux };
