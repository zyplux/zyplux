import { command, constant, message, object } from '@optique/core';
import { $, readTrimmed } from '@zyplux/util/shell';
import path from 'node:path';

import { syncPythonVersions, validatePythonVersions } from '#python-releases';
import { loadPreparedReleases } from '#release-notes';
import { loadRegistryArgs, loadReleaseTargets } from '#release-targets';

export const prepareReleaseCommand = command(
  'prepare-release',
  object({ command: constant('prepare-release' as const) }),
  {
    aliases: ['prepare'],
    brief: message`Prepare native pnpm changelogs, package versions and lockfiles for review.`,
  },
);

export const runPrepareRelease = async () => {
  const root = await readTrimmed($.git.showToplevel());
  const targets = await loadReleaseTargets();
  await validatePythonVersions(targets);
  const registryArgs = await loadRegistryArgs(targets);
  await $`pnpm version -r --no-git-checks ${registryArgs}`.cwd(root);
  await syncPythonVersions(targets, root);
  await $`pnpm install --lockfile-only`.cwd(root);
  if (targets.some(target => path.basename(target.versionFile) === 'pyproject.toml')) await $`uv lock`.cwd(root);
  await loadPreparedReleases();
};
