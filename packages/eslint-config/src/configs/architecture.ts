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
        .filter(target => /\.tsx?$/.test(target))
        .map(target => path.posix.join(directory, target)),
    );
  });
  return [
    { files: ['**/*.{ts,tsx}'], plugins: { '@zyplux': plugin }, rules: { '@zyplux/package-imports': 'error' } },
    {
      files: ['**/{types,interfaces}.ts', '**/interfaces/**/*.ts'],
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
