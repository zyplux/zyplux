import zodPlugin from 'eslint-plugin-zod';

import type { ConfigWithExtends } from './types.ts';

export const zodConfig: ConfigWithExtends = {
  files: ['**/*.{ts,tsx,js,mjs,cjs}'],
  plugins: { zod: zodPlugin },
  rules: {
    'zod/consistent-import': ['error', { syntax: 'namespace' }],
    'zod/no-any-schema': 'error',
    'zod/no-coerce-boolean': 'error',
    'zod/no-conflicting-checks': 'error',
    'zod/no-duplicate-schema-methods': 'error',
    'zod/no-throw-in-refine': 'error',
    'zod/no-transform-in-record-key': 'error',
  },
};
