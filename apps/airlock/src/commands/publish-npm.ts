import { command, constant, message, object } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { runPassthrough } from '@zyplux/util/exec';
import { parseJson } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import { mkdtempDisposable, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import type { ReleaseTarget } from '#release-targets';

import { NpmPackageSchema, WorkspacePackagesSchema } from '#contracts';
import { createGithubRelease } from '#github-releases';
import { loadNpmDependencies, orderNpmTargets, waitForNpmDependencies } from '#npm-dependencies';
import { loadPreparedTargets } from '#release-notes';

export const publishNpmCommand = command('publish-npm', object({ command: constant('publish-npm' as const) }), {
  brief: message`Publish declared npm targets in dependency order and reconcile their GitHub releases.`,
});

type NpmRelease = ReleaseTarget & { notes: string };

const validateNpmWorkspaces = async (releases: ReleaseTarget[], root: string) => {
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

export const publishNpm = async (targets: ReleaseTarget[]) => {
  if (targets.length === 0) return;
  await using directory = await mkdtempDisposable(path.join(tmpdir(), 'airlock-npm-'));
  const getArchive = ({ tag }: ReleaseTarget) => path.join(directory.path, `${encodeURIComponent(tag)}.tgz`);
  const dependencies = new Map<string, ReleaseTarget[]>();
  for (const target of targets) {
    const { scripts } = parseJson(await readFile(path.join(target.dir, 'package.json'), 'utf8'), NpmPackageSchema);
    ensure(
      ['prepublishOnly', 'publish', 'postpublish'].every(hook => !Object.hasOwn(scripts, hook)),
      `${target.label}: archive publication requires prepack/prepare/postpack hooks; publish-only hooks are unsupported`,
    );
    const archive = getArchive(target);
    await $`pnpm pack --out ${archive}`.cwd(target.dir);
    dependencies.set(target.label, await loadNpmDependencies(target, archive));
  }
  for (const target of orderNpmTargets(targets, dependencies)) {
    await waitForNpmDependencies(dependencies.get(target.label) ?? []);
    // pnpm's tarball HEAD probe is unsupported by GitHub Packages.
    await runPassthrough(['pnpm', 'publish', getArchive(target), '--publish-wait-timeout', '0'], target.dir);
    await waitForNpmDependencies([target]);
  }
};

export const publishNpmTargets = async (releases: NpmRelease[]) => {
  if (releases.length === 0) return;
  const root = await readTrimmed($.git.showToplevel());
  await validateNpmWorkspaces(releases, root);
  const pending = [];
  for (const release of releases) {
    if (await release.isPublished()) await waitForNpmDependencies([release]);
    else pending.push(release);
  }
  await publishNpm(pending);
  const head = await readTrimmed($.git.revParse('HEAD'));
  for (const release of releases) {
    if (!(await $.gh.release.exists(release.tag))) await createGithubRelease(release.tag, release.notes, head);
  }
};

export const runPublishNpm = async () => {
  const prepared = await loadPreparedTargets();
  return publishNpmTargets(prepared.filter(release => release.kind === 'npm'));
};
