import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import { ensure } from '@zyplux/util';
import { $ } from '@zyplux/util/shell';

import { resolveReleaseTag } from '#release-targets';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to publish (e.g. eslint-config-v1.2.3).`,
});

export const publishTaggedTargetCommand = command(
  'publish-tagged-target',
  object({ command: constant('publish-tagged-target' as const), tag: tagArgument }),
  {
    aliases: ['pt'],
    brief: message`Publish the target that owns a release tag to its registry (npm, PyPI, GHCR).`,
  },
);

type PublishTaggedTargetConfig = InferValue<typeof publishTaggedTargetCommand>;

export const publishNpm = async (dir: string) => {
  await $`cd ${dir} && bun pm pack && bunx npm@latest publish ./*.tgz --access public`;
};

const publishPypi = async (label: string) => {
  await $`uv build --package ${label} && uv publish`;
};

const publishGhcr = async (label: string, dir: string, version: string) => {
  const token = process.env['GH_TOKEN'];
  const actor = process.env['GITHUB_ACTOR'];
  ensure(token !== undefined && token.length > 0, 'GH_TOKEN is required to push to GHCR');
  ensure(actor !== undefined && actor.length > 0, 'GITHUB_ACTOR is required to push to GHCR');

  const versioned = `${label}:${version}`;
  const latest = `${label}:latest`;
  await $`podman login ghcr.io -u ${actor} --password-stdin < ${Buffer.from(token)}`;
  await $`podman build -t ${versioned} -t ${latest} ${dir}`;
  await $`podman push ${versioned}`;
  await $`podman push ${latest}`;
};

export const runPublishTaggedTarget = async ({ tag }: PublishTaggedTargetConfig) => {
  const { target, version } = await resolveReleaseTag(tag);

  if (await target.isPublished(version)) {
    console.log(`${target.label} ${version} is already published; nothing to do`);
    return;
  }

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
};
