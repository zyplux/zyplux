import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types.ts';

export const zypluxRules: ConfigWithExtends = {
  files: ['**/*.{ts,tsx,mts,cts}'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/max-nested-calls': 'error',
    '@zyplux/no-anonymous-param-type': 'error',
    '@zyplux/no-function-scoped-schema': 'error',
    '@zyplux/no-identity-cast': 'error',
    '@zyplux/no-return-array-push': 'error',
    '@zyplux/no-stray-pascal-const': 'error',
    '@zyplux/no-type-annotations': 'error',
    '@zyplux/no-type-predicate': 'error',
    '@zyplux/no-unvalidated-json': 'error',
    '@zyplux/no-zod-custom': 'error',
    '@zyplux/prefer-arrow-functions': ['error', { returnStyle: 'implicit' }],
    '@zyplux/prefer-destructured-params': 'error',
    '@zyplux/prefer-validate': 'error',
    '@zyplux/type-over-interface': 'error',
    'unicorn/max-nested-calls': 'off',
  },
};
