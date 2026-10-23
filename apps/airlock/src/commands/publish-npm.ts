import { command, constant, message, object } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { runPassthrough } from '@zyplux/util/exec';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import path from 'node:path';
import * as z from 'zod';

import type { ReleaseTarget } from '#release-targets';

import { createGithubRelease } from '#github-releases';
import { loadPreparedTargets } from '#release-notes';

export const publishNpmCommand = command('publish-npm', object({ command: constant('publish-npm' as const) }), {
  brief: message`Publish declared npm targets in dependency order and reconcile their GitHub releases.`,
});

type NpmRelease = ReleaseTarget & { notes: string };

const WorkspacePackagesSchema = z.array(
  z.object({ name: z.string().optional(), path: z.string(), private: z.boolean(), version: z.string().optional() }),
);

const validateNpmWorkspaces = async (releases: NpmRelease[], root: string) => {
  const workspaces = parseJson(
    await readTrimmed($`pnpm list --recursive --depth -1 --json`.cwd(root)),
    WorkspacePackagesSchema,
  );
  for (const release of releases) {
    const workspace = workspaces.find(workspace => path.resolve(workspace.path) === release.dir);
    ensure(workspace !== undefined, `${release.label}: ${release.dir} is not a pnpm workspace package`);
    ensure(workspace.name === release.label, `${release.label}: workspace package name is ${workspace.name}`);
    ensure(!workspace.private, `${release.label}: private workspace packages cannot be published`);
    ensure(workspace.version === release.version, `${release.label}: workspace version must be ${release.version}`);
  }
};

export const publishNpmTargets = async (releases: NpmRelease[]) => {
  if (releases.length === 0) return;
  const root = await readTrimmed($.git.showToplevel());
  await validateNpmWorkspaces(releases, root);
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
  await Promise.all(
    releases.map(async release => {
      ensure(await release.isPublished(), `${release.label} ${release.version} is missing from its registry`);
    }),
  );
  const head = await readTrimmed($.git.revParse('HEAD'));
  for (const release of releases) {
    if (!(await $.gh.release.exists(release.tag))) await createGithubRelease(release.tag, release.notes, head);
  }
};

export const runPublishNpm = async () => {
  const prepared = await loadPreparedTargets();
  return publishNpmTargets(prepared.filter(release => release.kind === 'npm'));
};
