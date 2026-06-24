import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import { ensure } from '@zyplux/util';

import { loadReleaseTargets } from '#release-targets';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to verify, e.g. eslint-config-v1.2.3.`,
});

export const assertTagCommand = command(
  'assert-tag',
  object({ command: constant('assert-tag' as const), tag: tagArgument }),
  { brief: message`Assert a release tag matches its target's declared version (from release-targets.toml).` },
);

type AssertTagConfig = InferValue<typeof assertTagCommand>;

export const runAssertTag = async ({ tag }: AssertTagConfig) => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => tag.startsWith(candidate.tagPrefix));
  ensure(target !== undefined, `no release target in release-targets.toml owns tag '${tag}'`);

  const version = await target.readVersion();
  const expected = `${target.tagPrefix}${version}`;
  ensure(tag === expected, `tag '${tag}' does not match ${target.label} version '${version}' (expected '${expected}')`);

  console.log(`${target.label} ${version} matches ${tag}`);
};
