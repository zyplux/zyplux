import { runPassthrough } from '@zyplux/util/exec';
import { $, readTrimmed } from '@zyplux/util/shell';
import { fileURLToPath } from 'node:url';

import { command, constant, message, object } from '#optique';
import { syncPythonVersions, validatePythonVersions } from '#python-releases';
import { loadPreparedReleases } from '#release-notes';
import { loadReleaseTargets } from '#release-targets';

export const prepareReleaseCommand = command(
  'prepare-release',
  object({ command: constant('prepare-release' as const) }),
  {
    brief: message`Prepare Changesets changelogs, package versions and lockfiles for review.`,
  },
);

export const runPrepareRelease = async () => {
  const root = await readTrimmed($.git.showToplevel());
  const targets = await loadReleaseTargets();
  await validatePythonVersions(targets);
  const changeset = fileURLToPath(import.meta.resolve('@changesets/cli/bin.js'));
  await runPassthrough([process.execPath, changeset, 'version'], root);
  await syncPythonVersions(targets, root);
  await $`pnpm install --lockfile-only`.cwd(root);
  if (targets.some(target => target.kind === 'pypi')) await $`uv lock`.cwd(root);
  await loadPreparedReleases();
};
