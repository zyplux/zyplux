import type { ESLint } from 'eslint';

import { version } from '#package.json';

import { rules } from './rules/index';

export const plugin = {
  meta: {
    name: '@zyplux/eslint-config',
    version,
  },
  rules,
} satisfies ESLint.Plugin;
