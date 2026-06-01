import eslint from '@eslint/js';

import type { ConfigWithExtends } from './types';

const arrowOnlyMessage = 'Use an arrow function. If `this`/`arguments`/`new.target` are needed, redesign.';

export const base: ConfigWithExtends = {
  extends: [eslint.configs.recommended],
  rules: {
    'no-empty-pattern': ['error', { allowObjectPatternsAsParameters: true }],
    'no-restricted-syntax': [
      'error',
      { message: arrowOnlyMessage, selector: 'FunctionDeclaration[generator=false]' },
      {
        message: arrowOnlyMessage,
        selector: ':not(MethodDefinition, Property[method=true]) > FunctionExpression[generator=false]',
      },
    ],
  },
};
