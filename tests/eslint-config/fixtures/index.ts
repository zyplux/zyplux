import type { LibraryFixtures } from '@zyplux/spectra/library-test-api';
import type { TestAPI } from 'vitest';

import { libraryTest, makeFixture } from '@zyplux/spectra/library-test-api';

import type { PrintedConfig } from './act.ts';

import { createFixRule, createLintRule, createMergedLint, parsePrintedConfig, printConfig, subjects } from './act.ts';
import { loadRulesSnapshot } from './arrange.ts';
import {
  applySuggestion,
  expectEachToReport,
  expectEachToReportNothing,
  isAbsolutePath,
  tsconfigRootDirs,
} from './matchers.ts';

type EslintFixtures = {
  applySuggestion: typeof applySuggestion;
  expectEachToReport: typeof expectEachToReport;
  expectEachToReportNothing: typeof expectEachToReportNothing;
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
  expectEachToReport: makeFixture(expectEachToReport),
  expectEachToReportNothing: makeFixture(expectEachToReportNothing),
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

export type { PrintedConfig, ZypluxConfig } from './act.ts';
export { lintMatchers } from './matchers.ts';
export type { Linter } from 'eslint';
export { describe, expect } from 'vitest';
