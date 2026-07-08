import path from 'node:path';
import * as z from 'zod';

import { describe, expect, parseJson, readJsonSync, test } from '#fixtures';

const rulesUrl = new URL('../../../packages/eslint-config/rules.json', import.meta.url);
const rootDirPlaceholder = '<rootDir>';
const printConfigTimeoutMs = 30_000;

const ParserOptionsSchema = z.looseObject({ tsconfigRootDir: z.string() });
const PrintedConfigSchema = z.looseObject({
  languageOptions: z.looseObject({ parserOptions: ParserOptionsSchema }),
});
type PrintedConfig = z.infer<typeof PrintedConfigSchema>;

const applyRootDirPlaceholder = (config: PrintedConfig) => {
  config.languageOptions.parserOptions.tsconfigRootDir = rootDirPlaceholder;
  return config;
};

const parsePrintedConfig = (printedConfig: string) => parseJson(printedConfig, PrintedConfigSchema);

describe('2. Dumping the fully resolved eslint config to a committed rules snapshot', () => {
  describe('2.1 keeping the committed snapshot in sync with the live resolved config', () => {
    test('2.1.1 matches the resolved config', { timeout: printConfigTimeoutMs }, ({ printedConfig }) => {
      expect(applyRootDirPlaceholder(parsePrintedConfig(printedConfig))).toStrictEqual(
        readJsonSync(rulesUrl, PrintedConfigSchema),
      );
    });
  });

  describe('2.2 keeping the snapshot portable across checkouts', () => {
    test(
      '2.2.1 replaces the absolute tsconfig root path with a stable placeholder',
      { timeout: printConfigTimeoutMs },
      ({ printedConfig }) => {
        const liveTsconfigRootDir = parsePrintedConfig(printedConfig).languageOptions.parserOptions.tsconfigRootDir;
        const snapshotTsconfigRootDir = readJsonSync(rulesUrl, PrintedConfigSchema).languageOptions.parserOptions
          .tsconfigRootDir;

        expect(path.isAbsolute(liveTsconfigRootDir)).toBe(true);
        expect(snapshotTsconfigRootDir).toBe(rootDirPlaceholder);
      },
    );
  });
});
