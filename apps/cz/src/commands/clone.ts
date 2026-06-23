import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { optional } from '@optique/core/modifiers';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import { existsSync } from 'node:fs';
import { rm } from 'node:fs/promises';
import path from 'node:path';

import { $ } from '#shell-harness';

const refArgument = argument(string({ metavar: 'REF' }), {
  description: message`Branch or tag to clone (defaults to the remote's default branch).`,
});

const repoArgument = argument(string({ metavar: 'REPO' }), {
  description: message`Repo to clone: owner/name, an https URL, or a git@ SSH URL.`,
});

export const cloneCommand = command(
  'clone',
  object({
    command: constant('clone' as const),
    ref: optional(refArgument),
    repo: repoArgument,
  }),
  {
    brief: message`Shallow-clone a reference repo into reference_clones/.`,
  },
);

type CloneConfig = InferValue<typeof cloneCommand>;

export const runClone = async ({ ref, repo }: CloneConfig) => {
  const isUrl = repo.includes('://') || repo.startsWith('git@');
  const url = isUrl ? repo : `https://github.com/${repo}.git`;
  const dest = `reference_clones/${path.basename(repo).replace(/\.git$/, '')}`;

  if (existsSync(dest)) {
    prompt(`${dest} exists — rm -rf and re-clone? [enter to continue, ^C to abort]`);
    await rm(dest, { force: true, recursive: true });
  }

  await $.git.clone(url, dest, { depth: 1, singleBranch: true, ...(ref !== undefined && { branch: ref }) });
};
