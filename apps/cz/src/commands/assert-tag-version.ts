import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';

import { resolveReleaseTag } from '#release-targets';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to verify (e.g. eslint-config-v1.2.3).`,
});

export const assertTagVersionCommand = command('assert-tag-version', object({ command: constant('assert-tag-version' as const), tag: tagArgument }), {
  aliases: ['av'],
  brief: message`Assert a release tag matches its target's declared version (from release-targets.toml).`,
});

type AssertTagVersionConfig = InferValue<typeof assertTagVersionCommand>;

export const runAssertTagVersion = async ({ tag }: AssertTagVersionConfig) => {
  const { target, version } = await resolveReleaseTag(tag);
  console.log(`${target.label} ${version} matches ${tag}`);
};
