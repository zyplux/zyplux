import type { InferValue } from '@optique/core';

import { message } from '@optique/core';

import { resolveReleaseTag } from '#release-targets';

import { makeReleaseTagCommand } from './release-tag-command.ts';

export const printTagKindCommand = makeReleaseTagCommand('print-tag-kind', {
  alias: 'pk',
  brief: message`Print the publication kind (npm, pypi, ghcr, action) of the target that owns a release tag.`,
  tagDescription: message`Release tag to classify (e.g. eslint-config-v1.2.3).`,
});

type PrintTagKindConfig = InferValue<typeof printTagKindCommand>;

export const runPrintTagKind = async ({ tag }: PrintTagKindConfig) => {
  const { kind } = await resolveReleaseTag(tag);
  console.log(kind);
};
