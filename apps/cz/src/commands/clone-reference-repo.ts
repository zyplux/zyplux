import type { InferValue } from '@optique/core/parser';

import { merge, object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { optional } from '@optique/core/modifiers';
import { argument, command, constant } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import { $ } from '@zyplux/util';
import { existsSync } from 'node:fs';
import { rm } from 'node:fs/promises';
import path from 'node:path';

const refArgument = argument(string({ metavar: 'REF' }), {
  description: message`Branch or tag to clone (defaults to the remote's default branch).`,
});

const repoArgument = argument(string({ metavar: 'REPO' }), {
  description: message`Repo to clone: owner/name, an https URL, or a git@ SSH URL.`,
});

const cloneParser = merge(
  object({ command: constant('clone-reference-repo' as const), repo: repoArgument }),
  object({ ref: optional(refArgument) }),
);

export const cloneReferenceRepoCommand = command('clone-reference-repo', cloneParser, {
  aliases: ['c', 'cr', 'clone'],
  brief: message`Shallow-clone a reference repo into reference_clones/.`,
});

type CloneReferenceRepoConfig = InferValue<typeof cloneReferenceRepoCommand>;

export const runCloneReferenceRepo = async ({ ref, repo }: CloneReferenceRepoConfig) => {
  const isUrl = repo.includes('://') || repo.startsWith('git@');
  const url = isUrl ? repo : `https://github.com/${repo}.git`;
  const dest = `reference_clones/${path.basename(repo).replace(/\.git$/, '')}`;

  if (existsSync(dest)) {
    prompt(`${dest} exists — rm -rf and re-clone? [enter to continue, ^C to abort]`);
    await rm(dest, { force: true, recursive: true });
  }

  await $.git.clone(url, dest, { depth: 1, singleBranch: true, ...(ref !== undefined && { branch: ref }) });
};
