import type { LibraryFixtures } from '@zyplux/tests-fixtures';
import type { TestAPI } from 'vitest';

import { libraryTest, makeFixture } from '@zyplux/tests-fixtures';

import type { PrintedConfig } from './act';

import {
  createFixRule,
  createLintRule,
  createMergedLint,
  loadRulesSnapshot,
  parsePrintedConfig,
  printConfig,
  subjects,
} from './act';
import { applySuggestion, isAbsolutePath, tsconfigRootDirs } from './assert';

type EslintFixtures = {
  applySuggestion: typeof applySuggestion;
  fixRule: ReturnType<typeof createFixRule>;
  isAbsolutePath: typeof isAbsolutePath;
  lint: Awaited<ReturnType<typeof createMergedLint>>;
  lintRule: ReturnType<typeof createLintRule>;
  plugin: typeof subjects.plugin;
  printedConfig: string;
  resolvedConfig: PrintedConfig;
  ruleId: string;
  ruleName: string;
  rulesSnapshot: PrintedConfig;
  tsconfigRootDirs: typeof tsconfigRootDirs;
  zyplux: typeof subjects.zyplux;
};

export const test: TestAPI<EslintFixtures & LibraryFixtures> = libraryTest.extend<EslintFixtures>({
  applySuggestion: makeFixture(applySuggestion),
  fixRule: async ({ ruleName }, use) => {
    await use(createFixRule(ruleName));
  },
  isAbsolutePath: makeFixture(isAbsolutePath),
  lint: async ({ ruleId }, use) => {
    await use(await createMergedLint(ruleId));
  },
  lintRule: async ({ ruleName }, use) => {
    await use(createLintRule(ruleName));
  },
  plugin: makeFixture(subjects.plugin),
  printedConfig: [
    async ({}, use) => {
      await use(printConfig());
    },
    { scope: 'file' },
  ],
  resolvedConfig: async ({ printedConfig }, use) => {
    await use(parsePrintedConfig(printedConfig));
  },
  ruleId: '',
  ruleName: '',
  rulesSnapshot: async ({}, use) => {
    await use(loadRulesSnapshot());
  },
  tsconfigRootDirs: makeFixture(tsconfigRootDirs),
  zyplux: makeFixture(subjects.zyplux),
});

export type { PrintedConfig, ZypluxConfig } from './act';
export { lintMatchers } from './assert';
export type { Linter } from 'eslint';
export { describe, expect } from 'vitest';
