import { buildExportMap, listExportTargets, listWorkspacePackages } from '@zyplux/util/workspace-architecture';
import path from 'node:path';

import { plugin } from '#plugin';

import type { ConfigWithExtends } from './types.ts';

export const architectureConfigs = (root: string): ConfigWithExtends[] => {
  const barrels = listWorkspacePackages(root).flatMap(packageInfo => {
    const directory = path.relative(root, packageInfo.directory).split(path.sep).join('/');
    const entries = buildExportMap(packageInfo.exports);
    const surfaces = directory.startsWith('packages/') ? ['.'] : [];
    return surfaces.flatMap(surface =>
      listExportTargets(entries[surface])
        .filter(target => /\.(?:[cm]?[jt]s|[jt]sx)$/.test(target))
        .map(target => path.posix.join(directory, target)),
    );
  });
  return [
    {
      files: ['**/*.{ts,tsx,mts,cts}'],
      plugins: { '@zyplux': plugin },
      rules: {
        '@zyplux/no-type-only-dependencies': 'error',
        '@zyplux/use-package-type-exports': 'error',
      },
    },
    {
      files: ['**/{types,interfaces}.{ts,tsx,mts,cts}', '**/interfaces/**/*.{ts,tsx,mts,cts}'],
      plugins: { '@zyplux': plugin },
      rules: { '@zyplux/type-only-modules': 'error' },
    },
    {
      files: ['**/constants.ts'],
      plugins: { '@zyplux': plugin },
      rules: { '@zyplux/constants-only-primitives': 'error' },
    },
    ...(barrels.length === 0
      ? []
      : [
          {
            files: barrels,
            plugins: { '@zyplux': plugin },
            rules: { '@zyplux/barrel-only-reexports': 'error' },
          } satisfies ConfigWithExtends,
        ]),
  ];
};
