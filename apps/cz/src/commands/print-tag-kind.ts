import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';

import { resolveReleaseTag } from '#release-targets';

const tagArgument = argument(string({ metavar: 'TAG' }), {
  description: message`Release tag to classify (e.g. eslint-config-v1.2.3).`,
});

export const printTagKindCommand = command('print-tag-kind', object({ command: constant('print-tag-kind' as const), tag: tagArgument }), {
  aliases: ['pk'],
  brief: message`Print the registry kind (npm, pypi, ghcr) of the target that owns a release tag.`,
});

type PrintTagKindConfig = InferValue<typeof printTagKindCommand>;

export const runPrintTagKind = async ({ tag }: PrintTagKindConfig) => {
  const { target } = await resolveReleaseTag(tag);
  console.log(target.kind);
};
