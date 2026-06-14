import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types';

export const zypluxRules: ConfigWithExtends = {
  files: ['**/*.{ts,tsx}'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/no-identity-cast': 'error',
    '@zyplux/no-inferrable-return-type': 'error',
    '@zyplux/no-type-predicate': 'error',
    '@zyplux/no-zod-custom': 'error',
    '@zyplux/prefer-arrow-functions': ['error', { returnStyle: 'implicit' }],
  },
};
