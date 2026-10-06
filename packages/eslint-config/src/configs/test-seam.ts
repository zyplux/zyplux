import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types.ts';

export const testSeamRules: ConfigWithExtends = {
  files: ['**/*.test.{ts,tsx}'],
  plugins: { '@zyplux': plugin },
  rules: {
    '@zyplux/test-seam-only-imports': 'error',
  },
};
