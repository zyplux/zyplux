// @story
// unparametrized
import type { PrintedConfig } from './configuration.ts';

import { describe, expect, test } from './configuration.ts';

const rootDirPlaceholder = '<rootDir>';
const printConfigTimeoutMs = 30_000;

const applyRootDirPlaceholder = (config: PrintedConfig) => {
  config.languageOptions.parserOptions.tsconfigRootDir = rootDirPlaceholder;
  return config;
};

describe('e2. Dumping the fully resolved eslint config to a committed rules snapshot', () => {
  describe('e2.1 keeping the committed snapshot in sync with the live resolved config', () => {
    test(
      'e2.1.1 matches the resolved config',
      { timeout: printConfigTimeoutMs },
      ({ resolvedConfig, rulesSnapshot }) => {
        expect(applyRootDirPlaceholder(resolvedConfig)).toStrictEqual(rulesSnapshot);
      },
    );
  });

  describe('e2.2 keeping the snapshot portable across checkouts', () => {
    test(
      'e2.2.1 replaces the absolute tsconfig root path with a stable placeholder',
      { timeout: printConfigTimeoutMs },
      ({ isAbsolutePath, resolvedConfig, rulesSnapshot }) => {
        expect(isAbsolutePath(resolvedConfig.languageOptions.parserOptions.tsconfigRootDir)).toBe(true);
        expect(rulesSnapshot.languageOptions.parserOptions.tsconfigRootDir).toBe(rootDirPlaceholder);
      },
    );
  });
});
