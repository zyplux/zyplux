import type { InferValue } from '@optique/core';

import { argument, command, constant, message, multiple, object, option, string } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { run, runPassthrough } from '@zyplux/util/exec';
import { $, readTrimmed } from '@zyplux/util/shell';
import { access } from 'node:fs/promises';

import { publishAction } from '#action-releases';
import { createGithubRelease, publishReleaseAssets } from '#github-releases';
import { validatePythonVersions } from '#python-releases';
import { loadReleaseNotes, validateConsumedIntents } from '#release-notes';
import { resolveReleaseTag } from '#release-targets';

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
    aliases: ['pt', 'publish'],
    brief: message`Publish the target that owns a release tag (npm, PyPI, GHCR or GitHub Action).`,
  },
);

type PublishTaggedTargetConfig = InferValue<typeof publishTaggedTargetCommand>;

export const publishNpm = (dir: string) => runPassthrough(['pnpm', 'publish', '--publish-wait-timeout', '600000'], dir);

const publishPypi = async (label: string) => {
  await $`uv build --package ${label}`;
  await $`uv publish`;
};

const podmanLogin = async (actor: string, token: string) => {
  await run(['podman', 'login', 'ghcr.io', '-u', actor, '--password-stdin'], { stdin: token });
};

const publishGhcr = async (label: string, dir: string, version: string) => {
  const token = process.env['GH_TOKEN'];
  const actor = process.env['GITHUB_ACTOR'];
  ensure(token !== undefined && token.length > 0, 'GH_TOKEN is required to push to GHCR');
  ensure(actor !== undefined && actor.length > 0, 'GITHUB_ACTOR is required to push to GHCR');

  const versioned = `${label}:${version}`;
  const latest = `${label}:latest`;
  await podmanLogin(actor, token);
  try {
    await $`podman build -t ${versioned} -t ${latest} ${dir}`;
    await $`podman push ${versioned}`;
    await $`podman push ${latest}`;
  } finally {
    await $`podman logout ghcr.io`;
  }
};

export const runPublishTaggedTarget = async ({ assets, shouldRelease, tag }: PublishTaggedTargetConfig) => {
  const { target, version } = await resolveReleaseTag(tag);
  ensure(assets.length === 0 || shouldRelease, '--asset requires --release');
  ensure(assets.length === 0 || target.action === undefined, 'action releases do not accept prebuilt assets');
  await Promise.all(assets.map(asset => access(asset)));
  if (shouldRelease) {
    await validateConsumedIntents();
    await validatePythonVersions([target]);
  }
  const notes = shouldRelease ? await loadReleaseNotes(target.dir, version) : undefined;

  if (target.action !== undefined) return publishAction(target.action, version, notes);

  const isPublished = await target.isPublished(version);
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
        await publishGhcr(target.label, target.dir, version);
        break;
      }
      case 'npm': {
        await publishNpm(target.dir);
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
