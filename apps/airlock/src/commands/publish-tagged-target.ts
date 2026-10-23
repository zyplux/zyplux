import type { InferValue } from '@optique/core';

import { argument, command, constant, message, multiple, object, option, string } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { run } from '@zyplux/util/exec';
import { $, readTrimmed } from '@zyplux/util/shell';
import { access, mkdtempDisposable } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import type { ReleaseTarget } from '#release-targets';

import { publishAction } from '#action-releases';
import { createGithubRelease, isReleasePublished, publishReleaseAssets } from '#github-releases';
import { validatePythonVersions } from '#python-releases';
import { loadReleaseNotes, validateConsumedIntents } from '#release-notes';
import { resolveReleaseTag } from '#release-targets';

import { publishNpm } from './publish-npm.ts';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to publish (e.g. eslint-config-v1.2.3).`,
});
const assetOption = option('--asset', string({ metavar: 'FILE' }));

export const publishTaggedTargetCommand = command(
  'publish-tagged-target',
  object({
    assets: multiple(assetOption),
    command: constant('publish-tagged-target' as const),
    shouldRelease: option('--release', {
      description: message`Create a GitHub release at HEAD after the artifact is published.`,
    }),
    tag: tagArgument,
  }),
  {
    aliases: ['pt'],
    brief: message`Publish the target that owns a release tag (npm, PyPI, GHCR or GitHub Action).`,
  },
);

type PublishTaggedTargetConfig = InferValue<typeof publishTaggedTargetCommand>;

const publishPypi = async (label: string) => {
  await using directory = await mkdtempDisposable(path.join(tmpdir(), 'release-pypi-'));
  await $`uv build --package ${label} --out-dir ${directory.path}`;
  await $`uv publish ${path.join(directory.path, '*')}`;
};

const podmanLogin = async (actor: string, token: string) => {
  await run(['podman', 'login', 'ghcr.io', '-u', actor, '--password-stdin'], { stdin: token });
};

const publishGhcr = async (target: ReleaseTarget, artifacts?: string) => {
  const { artifactCommand, dir, label, tag, version } = target;
  const token = process.env['GH_TOKEN'];
  const actor = process.env['GITHUB_ACTOR'];
  ensure(token !== undefined && token.length > 0, 'GH_TOKEN is required to push to GHCR');
  ensure(actor !== undefined && actor.length > 0, 'GITHUB_ACTOR is required to push to GHCR');

  const versioned = `${label}:${version}`;
  const latest = `${label}:latest`;
  await podmanLogin(actor, token);
  try {
    if (artifactCommand === undefined) {
      await $`podman build -t ${versioned} -t ${latest} ${dir}`;
      await $`podman push ${versioned}`;
      await $`podman push ${latest}`;
    } else {
      await run(artifactCommand, {
        cwd: await readTrimmed($.git.showToplevel()),
        env: {
          AIRLOCK_ARTIFACTS_DIR: artifacts,
          AIRLOCK_IMAGE: label,
          AIRLOCK_REVISION: await readTrimmed($.git.revParse('HEAD')),
          AIRLOCK_TAG: tag,
          AIRLOCK_VERSION: version,
        },
      });
    }
  } finally {
    await $`podman logout ghcr.io`;
  }
};

export const publishPreparedTarget = async (
  target: ReleaseTarget,
  notes: string | undefined,
  assets: readonly string[],
) => {
  const { tag, version } = target;
  ensure(assets.length === 0 || target.action === undefined, 'action releases do not accept prebuilt assets');
  await Promise.all(assets.map(asset => access(asset)));

  if (target.action !== undefined) return publishAction(target.action, version, notes);

  if (target.artifactCommand !== undefined) {
    ensure(notes !== undefined, 'artifact commands require --release');
    ensure(assets.length === 0, 'artifact commands use their declared assets');
    if (await isReleasePublished(tag, target.assets)) {
      ensure(await target.isPublished(), `published release ${tag} is missing image ${target.label}:${version}`);
      return;
    }
    await using directory = await mkdtempDisposable(path.join(tmpdir(), 'airlock-artifacts-'));
    const artifacts = target.assets.map(asset => {
      const artifact = path.resolve(directory.path, asset);
      ensure(artifact.startsWith(`${directory.path}${path.sep}`), 'assets must be relative to the artifact directory');
      return artifact;
    });
    await publishGhcr(target, directory.path);
    await Promise.all(artifacts.map(asset => access(asset)));
    ensure(await target.isPublished(), `artifact command did not publish image ${target.label}:${version}`);
    await publishReleaseAssets(tag, notes, await readTrimmed($.git.revParse('HEAD')), artifacts);
    return;
  }
  ensure(target.assets.length === 0, 'declared assets require an artifact_command');

  const isPublished = await target.isPublished();
  ensure(
    assets.length === 0 || target.kind !== 'ghcr' || isPublished,
    'publish the versioned image before attaching its release assets',
  );
  if (isPublished) {
    console.log(`${target.label} ${version} is already published; nothing to do`);
  } else {
    console.log(`Publishing ${target.label} ${version} to ${target.kind} ...`);
    switch (target.kind) {
      case 'ghcr': {
        await publishGhcr(target);
        break;
      }
      case 'npm': {
        await publishNpm([target]);
        break;
      }
      case 'pypi': {
        await publishPypi(target.label);
        break;
      }
    }
    console.log(`Published ${target.label} ${version}`);
  }
  if (notes === undefined) return;
  const head = await readTrimmed($.git.revParse('HEAD'));
  if (assets.length > 0) return publishReleaseAssets(tag, notes, head, [...assets]);
  if (await $.gh.release.exists(tag)) return;
  await createGithubRelease(tag, notes, head);
};

export const runPublishTaggedTarget = async ({ assets, shouldRelease, tag }: PublishTaggedTargetConfig) => {
  const target = await resolveReleaseTag(tag);
  ensure(assets.length === 0 || shouldRelease, '--asset requires --release');
  if (shouldRelease) {
    await validateConsumedIntents();
    await validatePythonVersions([target]);
  }
  const notes = shouldRelease ? await loadReleaseNotes(target.dir, target.version) : undefined;
  return publishPreparedTarget(target, notes, assets);
};
