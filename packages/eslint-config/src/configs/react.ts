import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

import type { ConfigWithExtends } from './types';

export const reactConfig = (files: string[], version: string) => {
  const recommended = react.configs.flat.recommended;
  if (!recommended) {
    throw new Error('eslint-plugin-react: configs.flat.recommended is missing');
  }
  const jsxRuntime = react.configs.flat['jsx-runtime'];
  if (!jsxRuntime) {
    throw new Error('eslint-plugin-react: configs.flat[jsx-runtime] is missing');
  }
  return {
    extends: [recommended, jsxRuntime, reactHooks.configs.flat['recommended-latest']],
    files,
    settings: { react: { version } },
  } satisfies ConfigWithExtends;
};

export const nonDomReactConfig = (files: string[]) =>
  ({
    files,
    rules: { 'react/no-unknown-property': 'off' },
  }) satisfies ConfigWithExtends;
