import type { PrintedConfig } from '#fixtures';

import path from 'node:path';

import { describe, expect, test } from '#fixtures';

const rootDirPlaceholder = '<rootDir>';
const printConfigTimeoutMs = 30_000;

const applyRootDirPlaceholder = (config: PrintedConfig) => {
  config.languageOptions.parserOptions.tsconfigRootDir = rootDirPlaceholder;
  return config;
};

describe('2. Dumping the fully resolved eslint config to a committed rules snapshot', () => {
  describe('2.1 keeping the committed snapshot in sync with the live resolved config', () => {
    test('2.1.1 matches the resolved config', { timeout: printConfigTimeoutMs }, ({ resolvedConfig, rulesSnapshot }) => {
      expect(applyRootDirPlaceholder(resolvedConfig)).toStrictEqual(rulesSnapshot);
    });
  });

  describe('2.2 keeping the snapshot portable across checkouts', () => {
    test(
      '2.2.1 replaces the absolute tsconfig root path with a stable placeholder',
      { timeout: printConfigTimeoutMs },
      ({ resolvedConfig, rulesSnapshot }) => {
        expect(path.isAbsolute(resolvedConfig.languageOptions.parserOptions.tsconfigRootDir)).toBe(true);
        expect(rulesSnapshot.languageOptions.parserOptions.tsconfigRootDir).toBe(rootDirPlaceholder);
      },
    );
  });
});
