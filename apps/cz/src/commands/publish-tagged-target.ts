import { ensure } from '@zyplux/util/assert';
import { run, runPassthrough } from '@zyplux/util/exec';
import { $ } from '@zyplux/util/shell';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import type { InferValue } from '#optique';

import { argument, command, constant, message, object, string } from '#optique';
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
  const archiveDir = await mkdtemp(path.join(tmpdir(), 'cz-npm-'));
  try {
    const archive = path.join(archiveDir, 'package.tgz');
    await $`pnpm pack --out ${archive}`.cwd(dir);
    await runPassthrough(['npm', 'publish', archive, '--access', 'public'], dir);
  } finally {
    await rm(archiveDir, { force: true, recursive: true });
  }
};

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
