import { zyplux } from '@zyplux/eslint-config';
import { libraryTest, makeFixture } from '@zyplux/spectra';

import { createFixRule, createLintRule, createMergedLint } from '#lint-engine';

import {
  applySuggestion,
  expectEachToReport,
  expectEachToReportNothing,
  registerLintMatchers,
} from './lint-matchers.ts';
export const test = libraryTest
  .extend('zyplux', () => zyplux)
  .extend<{
    applySuggestion: typeof applySuggestion;
    expectEachToReport: typeof expectEachToReport;
    expectEachToReportNothing: typeof expectEachToReportNothing;
    fixRule: ReturnType<typeof createFixRule>;
    lint: Awaited<ReturnType<typeof createMergedLint>>;
    lintMatchers: undefined;
    lintRule: ReturnType<typeof createLintRule>;
    ruleId: string;
    ruleName: string;
  }>({
    applySuggestion: makeFixture(applySuggestion),
    expectEachToReport: makeFixture(expectEachToReport),
    expectEachToReportNothing: makeFixture(expectEachToReportNothing),
    fixRule: async ({ ruleName }, use) => {
      await use(createFixRule(ruleName));
    },
    lint: async ({ ruleId }, use) => {
      await use(await createMergedLint(ruleId));
    },
    lintMatchers: [
      async ({}, use) => {
        registerLintMatchers();
        await use(undefined);
      },
      { auto: true },
    ],
    lintRule: async ({ ruleName }, use) => {
      await use(createLintRule(ruleName));
    },
    ruleId: '',
    ruleName: '',
  });
export type { Linter } from 'eslint';
export { describe, expect } from 'vitest';
