import type { InferValue } from '@optique/core';

import { argument, command, constant, message, object, option, string } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { $, readTrimmed } from '@zyplux/util/shell';
import { mkdtempDisposable } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import type { ReleaseTarget } from '#release-targets';

import { publishAction } from '#action-releases';
import { publishContainer } from '#container-releases';
import { createGithubRelease } from '#github-releases';
import { validatePythonVersions } from '#python-releases';
import { loadReleaseNotes, validateConsumedIntents } from '#release-notes';
import { resolveReleaseTag } from '#release-targets';

import { publishNpm } from './publish-npm.ts';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to publish (e.g. eslint-config-v1.2.3).`,
});

export const publishTaggedTargetCommand = command(
  'publish-tagged-target',
  object({
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

export const publishPreparedTarget = async (target: ReleaseTarget, notes: string | undefined) => {
  const { tag, version } = target;
  if (target.action !== undefined) return publishAction(target.action, version, notes);
  if (target.kind === 'ghcr') {
    ensure(notes !== undefined, 'container publication requires --release');
    return publishContainer(target, notes);
  }

  const isPublished = await target.isPublished();
  if (isPublished) {
    console.log(`${target.label} ${version} is already published; nothing to do`);
  } else {
    console.log(`Publishing ${target.label} ${version} to ${target.kind} ...`);
    switch (target.kind) {
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
  if (await $.gh.release.exists(tag)) return;
  await createGithubRelease(tag, notes, head);
};

export const runPublishTaggedTarget = async ({ shouldRelease, tag }: PublishTaggedTargetConfig) => {
  const target = await resolveReleaseTag(tag);
  if (shouldRelease) {
    await validateConsumedIntents();
    await validatePythonVersions([target]);
  }
  const notes = shouldRelease ? await loadReleaseNotes(target.dir, target.version) : undefined;
  return publishPreparedTarget(target, notes);
};
