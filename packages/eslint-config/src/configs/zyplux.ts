import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types';

export const zypluxRules: ConfigWithExtends = {
  files: ['**/*.{ts,tsx}'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/no-anonymous-param-type': 'error',
    '@zyplux/no-identity-cast': 'error',
    '@zyplux/no-return-array-push': 'error',
    '@zyplux/no-stray-pascal-const': 'error',
    '@zyplux/no-type-annotations': 'error',
    '@zyplux/no-type-predicate': 'error',
    '@zyplux/no-unvalidated-json': 'error',
    '@zyplux/no-zod-custom': 'error',
    '@zyplux/prefer-arrow-functions': ['error', { returnStyle: 'implicit' }],
    '@zyplux/prefer-destructured-params': 'error',
    '@zyplux/type-over-interface': 'error',
  },
};

export const packageWideUnusedTypesRules: ConfigWithExtends = {
  files: ['**/*.{ts,tsx}'],
  ignores: ['**/src/contracts.ts'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/no-package-wide-unused-types': 'error',
  },
};
