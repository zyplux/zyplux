import type { InferValue } from '#optique';

import { makeReleaseTagCommand } from '#commands/release-tag-command';
import { message } from '#optique';
import { resolveReleaseTag } from '#release-targets';

export const printTagKindCommand = makeReleaseTagCommand('print-tag-kind', {
  alias: 'pk',
  brief: message`Print the registry kind (npm, pypi, ghcr) of the target that owns a release tag.`,
  tagDescription: message`Release tag to classify (e.g. eslint-config-v1.2.3).`,
});

type PrintTagKindConfig = InferValue<typeof printTagKindCommand>;

export const runPrintTagKind = async ({ tag }: PrintTagKindConfig) => {
  const { target } = await resolveReleaseTag(tag);
  console.log(target.kind);
};
