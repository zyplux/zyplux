import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types';

export const testSeamRules: ConfigWithExtends = {
  files: ['**/stories/*.test.{ts,tsx}'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/test-seam-only-imports': 'error',
  },
};
