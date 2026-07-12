import type { LibraryFixtures } from '@zyplux/tests-fixtures';
import type { TestAPI } from 'vitest';

import { libraryTest, makeFixture } from '@zyplux/tests-fixtures';

import type { PackageLint, PrintedConfig } from './act';

import {
  createFixRule,
  createLintRule,
  createMergedLint,
  createPackageLint,
  parsePrintedConfig,
  printConfig,
} from './act';
import { loadRulesSnapshot, subjects, writePackageSource } from './arrange';
import {
  applySuggestion,
  expectEachToReport,
  expectEachToReportNothing,
  expectPackageOutcome,
  isAbsolutePath,
  tsconfigRootDirs,
} from './matchers';

type EslintFixtures = {
  applySuggestion: typeof applySuggestion;
  expectEachToReport: typeof expectEachToReport;
  expectEachToReportNothing: typeof expectEachToReportNothing;
  expectPackageOutcome: typeof expectPackageOutcome;
  fixRule: ReturnType<typeof createFixRule>;
  isAbsolutePath: typeof isAbsolutePath;
  lint: Awaited<ReturnType<typeof createMergedLint>>;
  lintPackage: (packageSource: Record<string, string>) => PackageLint;
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
  expectPackageOutcome: makeFixture(expectPackageOutcome),
  fixRule: async ({ ruleName }, use) => {
    await use(createFixRule(ruleName));
  },
  isAbsolutePath: makeFixture(isAbsolutePath),
  lint: async ({ ruleId }, use) => {
    await use(await createMergedLint(ruleId));
  },
  lintPackage: async ({}, use) => {
    const cleanups: (() => void)[] = [];
    await use(packageSource => {
      const { cleanup, tsconfigRootDir } = writePackageSource(packageSource);
      cleanups.push(cleanup);
      return createPackageLint(tsconfigRootDir, packageSource);
    });
    for (const cleanup of cleanups) cleanup();
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

export type { PrintedConfig } from './act';
export type { ZypluxConfig } from './arrange';
export { lintMatchers } from './matchers';
export type { Linter } from 'eslint';
export { describe, expect } from 'vitest';
