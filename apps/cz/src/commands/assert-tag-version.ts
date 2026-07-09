import type { InferValue } from '#optique';

import { makeReleaseTagCommand } from '#commands/release-tag-command';
import { message } from '#optique';
import { resolveReleaseTag } from '#release-targets';

export const assertTagVersionCommand = makeReleaseTagCommand('assert-tag-version', {
  alias: 'av',
  brief: message`Assert a release tag matches its target's declared version (from release-targets.toml).`,
  tagDescription: message`Release tag to verify (e.g. eslint-config-v1.2.3).`,
});

type AssertTagVersionConfig = InferValue<typeof assertTagVersionCommand>;

export const runAssertTagVersion = async ({ tag }: AssertTagVersionConfig) => {
  const { target, version } = await resolveReleaseTag(tag);
  console.log(`${target.label} ${version} matches ${tag}`);
};
