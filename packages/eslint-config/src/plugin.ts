import type { ESLint } from 'eslint';

import { loadPackageVersion } from '@zyplux/util/manifest';

import { rules } from './rules/index.ts';

export const plugin: ESLint.Plugin = {
  meta: {
    name: '@zyplux/eslint-config',
    version: loadPackageVersion(import.meta.url),
  },
  rules,
};
