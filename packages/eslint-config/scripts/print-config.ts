import { parseJson } from '@zyplux/util';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { PrintedConfigSchema } from '#contracts';

const ROOT_DIR_PLACEHOLDER = '<rootDir>';
const packageDir = fileURLToPath(new URL('..', import.meta.url));

export const printConfig = () => {
  const printed = execFileSync('eslint', ['--print-config', 'src/index.ts'], { cwd: packageDir, encoding: 'utf8' });
  const config = parseJson(printed, PrintedConfigSchema);
  config.languageOptions.parserOptions.tsconfigRootDir = ROOT_DIR_PLACEHOLDER;
  return config;
};
