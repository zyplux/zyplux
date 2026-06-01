import prettier from 'eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';

import { base } from './configs/base';
import { perfectionistConfig } from './configs/perfectionist';
import { nonDomReactConfig, reactConfig } from './configs/react';
import { tanstackRoutes } from './configs/tanstack';
import { totvibeRules } from './configs/totvibe';
import { typescript } from './configs/typescript';
import { type FilenameCases, unicornConfig } from './configs/unicorn';

export type { FilenameCase, FilenameCases } from './configs/unicorn';
export { plugin } from './plugin';

const defaultIgnores = [
  '**/.output',
  '**/.nitro',
  '**/.vinxi',
  '**/.tanstack',
  '**/.wrangler',
  '**/.venv',
  '**/dist',
  '**/node_modules',
  '**/routeTree.gen.ts',
  '**/worker-configuration.d.ts',
];

export type TotvibeOptions = {
  filenameCase?: FilenameCases;
  ignores?: string[];
  nonDomReactFiles?: string[];
  react?: boolean;
  reactFiles?: string[];
  reactVersion?: string;
  tanstack?: boolean;
  tsconfigRootDir?: string;
};

const reactFilenameCases: FilenameCases = { camelCase: true, kebabCase: true, pascalCase: true };

export const totvibe = (options: TotvibeOptions = {}) => {
  const {
    filenameCase,
    ignores = [],
    nonDomReactFiles = [],
    react = false,
    reactFiles = ['**/src/**/*.{ts,tsx}'],
    reactVersion = 'detect',
    tanstack = false,
    tsconfigRootDir = process.cwd(),
  } = options;

  const resolvedFilenameCase = filenameCase ?? (react ? reactFilenameCases : undefined);

  return defineConfig(
    globalIgnores([...defaultIgnores, ...ignores]),
    base,
    typescript(tsconfigRootDir),
    ...(react ? [reactConfig(reactFiles, reactVersion)] : []),
    perfectionistConfig,
    unicornConfig(resolvedFilenameCase),
    ...(tanstack ? [tanstackRoutes] : []),
    ...(react && nonDomReactFiles.length > 0 ? [nonDomReactConfig(nonDomReactFiles)] : []),
    totvibeRules,
    prettier,
  );
};
