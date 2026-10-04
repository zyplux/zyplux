import unicorn from 'eslint-plugin-unicorn';

import type { ConfigWithExtends } from './types.ts';

export const unicornConfig: ConfigWithExtends = {
  extends: [unicorn.configs.recommended],
  files: ['**/*.{ts,tsx,js,mjs,cjs}'],
  rules: {
    'unicorn/catch-error-name': 'off',
    'unicorn/consistent-class-member-order': 'off',
    'unicorn/name-replacements': 'off',
    'unicorn/no-return-array-push': 'off',
    'unicorn/prevent-abbreviations': 'off',
  },
};
