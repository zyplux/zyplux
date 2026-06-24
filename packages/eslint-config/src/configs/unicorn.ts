import unicorn from 'eslint-plugin-unicorn';

import type { ConfigWithExtends } from './types';

export const unicornConfig: ConfigWithExtends = {
  extends: [unicorn.configs.all],
  files: ['**/*.{ts,tsx,js,mjs,cjs}'],
  rules: {
    'unicorn/catch-error-name': 'off',
    'unicorn/name-replacements': 'off',
    'unicorn/no-return-array-push': 'off',
    'unicorn/prevent-abbreviations': 'off',
  },
};
