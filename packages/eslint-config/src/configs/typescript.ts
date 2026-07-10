import type { Linter } from 'eslint';

import tseslint from 'typescript-eslint';

import type { ConfigWithExtends } from './types';

const allOverrides: Linter.RulesRecord = {
  '@typescript-eslint/consistent-return': 'off', // recommended noImplicitReturns over this rule https://typescript-eslint.io/rules/consistent-return
  '@typescript-eslint/explicit-function-return-type': 'off',
  '@typescript-eslint/explicit-module-boundary-types': 'off',
  '@typescript-eslint/naming-convention': [
    'error',
    { format: ['camelCase'], leadingUnderscore: 'allow', selector: 'default' },
    { format: ['camelCase', 'PascalCase', 'UPPER_CASE'], selector: 'variable' },
    { format: [], modifiers: ['destructured'], selector: 'variable' },
    { format: ['camelCase', 'PascalCase'], selector: 'function' },
    { format: ['camelCase'], leadingUnderscore: 'allow', selector: 'parameter' },
    { format: ['PascalCase'], selector: 'typeLike' },
    { format: ['camelCase', 'PascalCase'], selector: 'import' },
    { format: [], selector: ['objectLiteralMethod', 'objectLiteralProperty', 'typeProperty'] },
  ],
  '@typescript-eslint/no-magic-numbers': [
    'error',
    {
      ignore: [-1, 0, 1],
      ignoreNumericLiteralTypes: true,
      ignoreTypeIndexes: true,
    },
  ],
  '@typescript-eslint/prefer-readonly-parameter-types': 'off',
};

const strictStylisticOverrides: Linter.RulesRecord = {
  '@typescript-eslint/consistent-type-assertions': ['error', { assertionStyle: 'never' }],
  '@typescript-eslint/consistent-type-definitions': 'off',
  '@typescript-eslint/no-restricted-imports': [
    'error',
    {
      patterns: [
        {
          message: 'No parent-relative (../) imports — route through a tsconfig "paths" alias (e.g. @/foo) instead.',
          regex: String.raw`^\.\.`,
        },
      ],
    },
  ],
  '@typescript-eslint/prefer-destructuring': 'off',
  '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
};

export const typescript = (tsconfigRootDir: string): ConfigWithExtends => ({
  extends: [tseslint.configs.strictTypeChecked, tseslint.configs.stylisticTypeChecked],
  //extends: [tseslint.configs.all],
  files: ['**/*.{ts,tsx}'],
  languageOptions: {
    parserOptions: {
      projectService: true,
      tsconfigRootDir,
    },
  },
  rules: {
    ...allOverrides,
    ...strictStylisticOverrides,
  },
});
