import unicorn from 'eslint-plugin-unicorn';

import type { ConfigWithExtends } from './types';

export type FilenameCase = 'camelCase' | 'kebabCase' | 'pascalCase' | 'snakeCase';

export type FilenameCases = Partial<Record<FilenameCase, boolean>>;

export const unicornConfig = (filenameCase?: FilenameCases) =>
  ({
    extends: [unicorn.configs.recommended],
    files: ['**/*.{ts,tsx,js,mjs,cjs}'],
    rules: {
      'unicorn/catch-error-name': 'off',
      'unicorn/prevent-abbreviations': 'off',
      ...(filenameCase && { 'unicorn/filename-case': ['error', { cases: filenameCase }] }),
    },
  }) satisfies ConfigWithExtends;
