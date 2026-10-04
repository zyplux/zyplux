import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types.ts';

export const contractsRules: ConfigWithExtends = {
  files: ['**/contracts.ts', '**/contracts/**/*.ts'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/contracts-only-schemas': 'error',
  },
};

export const schemaBoundaryRules: ConfigWithExtends = {
  files: ['**/*.{ts,tsx}'],
  ignores: ['**/contracts.ts', '**/contracts/**/*.ts'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/no-schemas-outside-contracts': 'error',
  },
};
