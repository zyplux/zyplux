import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types';

export const contractsRules: ConfigWithExtends = {
  files: ['**/src/contracts.ts'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/contracts-only-schemas': 'error',
  },
};
