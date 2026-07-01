import { parseJson, readJsonSync } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeAll, describe, expect, it } from 'vitest';
import * as z from 'zod';

const eslintConfigDir = fileURLToPath(new URL('../../../packages/eslint-config/', import.meta.url));
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

describe('2. Dumping the fully resolved eslint config to a committed rules snapshot', () => {
  let printedConfigJson: string;

  beforeAll(() => {
    printedConfigJson = execFileSync('eslint', ['--print-config', 'src/index.ts'], {
      cwd: eslintConfigDir,
      encoding: 'utf8',
    });
  }, printConfigTimeoutMs);

  const parsePrintedConfig = () => parseJson(printedConfigJson, PrintedConfigSchema);

  describe('2.1 keeping the committed snapshot in sync with the live resolved config', () => {
    it('2.1.1 matches the resolved config', () => {
      expect(applyRootDirPlaceholder(parsePrintedConfig())).toStrictEqual(readJsonSync(rulesUrl, PrintedConfigSchema));
    });
  });

  describe('2.2 keeping the snapshot portable across checkouts', () => {
    it('2.2.1 replaces the absolute tsconfig root path with a stable placeholder', () => {
      const config = parsePrintedConfig();
      const rawTsconfigRootDir = config.languageOptions.parserOptions.tsconfigRootDir;

      expect(path.isAbsolute(rawTsconfigRootDir)).toBe(true);
      expect(applyRootDirPlaceholder(config).languageOptions.parserOptions.tsconfigRootDir).toBe(rootDirPlaceholder);
    });
  });
});
