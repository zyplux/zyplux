import prettier from 'eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';

import { base } from './configs/base';
import { gitignore } from './configs/gitignore';
import { perfectionistConfig } from './configs/perfectionist';
import { reactPresets, type RendererGlobs } from './configs/react';
import { tanstackRoutes } from './configs/tanstack';
import { typescript } from './configs/typescript';
import { unicornConfig } from './configs/unicorn';
import { vitestConfig } from './configs/vitest';
import { zypluxRules } from './configs/zyplux';

export type { ReactRenderer, RendererGlobs } from './configs/react';
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

const defaultDomFiles = ['**/src/**/*.{ts,tsx}'];

export type ReactOption = boolean | RendererGlobs;

export type ZypluxOptions = {
  ignores?: string[];
  nonDomReactFiles?: string[];
  react?: ReactOption;
  reactFiles?: string[];
  reactVersion?: string;
  tanstack?: boolean;
  tsconfigRootDir?: string;
};

const resolveRenderers = (react: ReactOption, domFiles: string[], nonDomFiles: string[]) => {
  if (react === false) return {};
  if (react === true) {
    return { dom: domFiles, ...(nonDomFiles.length > 0 && { opentui: nonDomFiles }) };
  }
  return react;
};

const create = (options: ZypluxOptions = {}) => {
  const {
    ignores = [],
    nonDomReactFiles = [],
    react = false,
    reactFiles = defaultDomFiles,
    reactVersion = 'detect',
    tanstack: isTanstack = false,
    tsconfigRootDir = process.cwd(),
  } = options;

  const renderers = resolveRenderers(react, reactFiles, nonDomReactFiles);

  return defineConfig(
    gitignore(tsconfigRootDir),
    globalIgnores([...defaultIgnores, ...ignores]),
    base,
    typescript(tsconfigRootDir),
    ...reactPresets(renderers, reactVersion),
    perfectionistConfig,
    unicornConfig,
    ...(isTanstack ? [tanstackRoutes] : []),
    zypluxRules,
    vitestConfig,
    prettier,
  );
};

export const zyplux = Object.assign(create, {
  withDefaults:
    (defaults: ZypluxOptions) =>
    (options: ZypluxOptions = {}) =>
      create({ ...defaults, ...options }),
});
