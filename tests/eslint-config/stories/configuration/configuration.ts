import type { PrintedConfig } from '@zyplux/eslint-config/contracts';
import type { LibraryFixtures } from '@zyplux/spectra';
import type { TestAPI } from 'vitest';

import { plugin, zyplux } from '@zyplux/eslint-config';
import { ParserOptionsSchema, PrintedConfigSchema } from '@zyplux/eslint-config/contracts';
import { libraryTest, makeFixture } from '@zyplux/spectra';
import { parseJson, readJsonSync } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
export type ZypluxConfig = ReturnType<typeof zyplux>;
const eslintConfigDir = fileURLToPath(new URL('../../../../packages/eslint-config/', import.meta.url));
const rulesSnapshotUrl = new URL('../../../../packages/eslint-config/rules.json', import.meta.url);
const isAbsolutePath = (candidate: string) => path.isAbsolute(candidate);

const tsconfigRootDirs = (config: ZypluxConfig) =>
  config.flatMap(entry => {
    const parsed = ParserOptionsSchema.safeParse(entry.languageOptions?.['parserOptions']);
    return parsed.success ? [parsed.data.tsconfigRootDir] : [];
  });

type ConfigurationFixtures = {
  isAbsolutePath: typeof isAbsolutePath;
  plugin: typeof plugin;
  printedConfig: string;
  resolvedConfig: PrintedConfig;
  rulesSnapshot: PrintedConfig;
  tsconfigRootDirs: typeof tsconfigRootDirs;
  zyplux: typeof zyplux;
};

export const test: TestAPI<ConfigurationFixtures & LibraryFixtures> = libraryTest.extend<ConfigurationFixtures>({
  isAbsolutePath: makeFixture(isAbsolutePath),
  plugin: makeFixture(plugin),
  printedConfig: [
    async ({}, use) => {
      await use(execFileSync('eslint', ['--print-config', 'src/index.ts'], { cwd: eslintConfigDir, encoding: 'utf8' }));
    },
    { scope: 'file' },
  ],
  resolvedConfig: async ({ printedConfig }, use) => {
    await use(parseJson(printedConfig, PrintedConfigSchema));
  },
  rulesSnapshot: async ({}, use) => {
    await use(readJsonSync(rulesSnapshotUrl, PrintedConfigSchema));
  },
  tsconfigRootDirs: makeFixture(tsconfigRootDirs),
  zyplux: makeFixture(zyplux),
});
export type { PrintedConfig } from '@zyplux/eslint-config/contracts';
export { describe, expect } from 'vitest';
