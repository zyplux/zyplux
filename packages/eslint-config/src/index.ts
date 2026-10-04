import prettier from 'eslint-config-prettier';
import { defineConfig, globalIgnores } from 'eslint/config';

import { base } from './configs/base.ts';
import { fixtureRoleConfigs } from './configs/fixture-roles.ts';
import { gitignore } from './configs/gitignore.ts';
import { perfectionistConfig } from './configs/perfectionist.ts';
import { reactPresets, type RendererGlobs } from './configs/react.ts';
import { contractsRules, schemaBoundaryRules } from './configs/schema-boundary.ts';
import { tanstackRoutes } from './configs/tanstack.ts';
import { testSeamRules } from './configs/test-seam.ts';
import { typescript } from './configs/typescript.ts';
import { unicornConfig } from './configs/unicorn.ts';
import { vitestConfig } from './configs/vitest.ts';
import { zypluxRules } from './configs/zyplux.ts';

export type { ReactRenderer, RendererGlobs } from './configs/react.ts';
export { plugin } from './plugin.ts';

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
  return react === true ? { dom: domFiles, ...(nonDomFiles.length > 0 && { opentui: nonDomFiles }) } : react;
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
    contractsRules,
    schemaBoundaryRules,
    testSeamRules,
    ...fixtureRoleConfigs(tsconfigRootDir),
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
