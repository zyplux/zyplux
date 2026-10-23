import { command, constant, message, object } from '@optique/core';
import { runPassthrough } from '@zyplux/util/exec';
import { $, readTrimmed } from '@zyplux/util/shell';

import { createGithubRelease } from '#github-releases';
import { loadPreparedReleases } from '#release-notes';

export const publishNpmCommand = command('publish-npm', object({ command: constant('publish-npm' as const) }), {
  brief: message`Publish declared npm targets in dependency order and reconcile their GitHub releases.`,
});

type NpmRelease = { label: string; notes: string; tag: string };

export const publishNpmTargets = async (releases: NpmRelease[]) => {
  if (releases.length === 0) return;
  const root = await readTrimmed($.git.showToplevel());
  await runPassthrough(
    [
      'pnpm',
      ...releases.flatMap(release => ['--filter', release.label]),
      'publish',
      '--recursive',
      '--report-summary',
      '--publish-wait-timeout',
      '600000',
    ],
    root,
  );
  const head = await readTrimmed($.git.revParse('HEAD'));
  for (const release of releases) {
    if (!(await $.gh.release.exists(release.tag))) await createGithubRelease(release.tag, release.notes, head);
  }
};

export const runPublishNpm = async () => {
  const prepared = await loadPreparedReleases();
  return publishNpmTargets(prepared.filter(release => release.kind === 'npm'));
};
