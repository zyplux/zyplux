import { $, checkInsideWorkTree, ensure, findGitRepos, readTrimmed } from '@zyplux/util';
import path from 'node:path';

import type { InferValue } from '#optique';

import { command, constant, message, multiple, object, option, string } from '#optique';

// Ignored files are the authoritative "generated/cache" list per repo (its own .gitignore),
// so cleaning stays in sync automatically instead of drifting from a hardcoded dir-name list.
// Dotenv files are gitignored too but hold secrets a fresh checkout can't reproduce, so they're
// always protected; --exclude adds more protected paths (a whole repo, or a subfolder) on top.
const ALWAYS_PROTECTED = ['.env', '.env.*'];

const excludeOption = multiple(
  option('--exclude', string({ metavar: 'DIR' }), {
    description: message`Skip a repo by directory name, or protect a path from removal within one. Repeatable.`,
  }),
);

export const cleanCommand = command(
  'clean',
  object({
    command: constant('clean' as const),
    dryRun: option('--dry-run', {
      description: message`Show what would be removed without removing anything.`,
    }),
    exclude: excludeOption,
  }),
  {
    aliases: ['cl'],
    brief: message`Remove gitignored build artifacts and caches from this repo, or every repo under the current directory.`,
  },
);

type CleanConfig = InferValue<typeof cleanCommand>;
type CleanRepoOptions = { dryRun: boolean; protect: string[] };

const cleanRepo = async (repo: string, options: CleanRepoOptions) => {
  const result = await $.git.clean(repo, options);
  return result
    .text()
    .split('\n')
    .filter(line => line.length > 0);
};

export const runClean = async ({ dryRun, exclude }: CleanConfig) => {
  const cwd = process.cwd();

  const repos = (await checkInsideWorkTree(cwd))
    ? [await readTrimmed($.git.showToplevel(cwd))]
    : await findGitRepos(cwd);
  ensure(repos.length > 0, `no git repo found at or under ${cwd}`);

  const repoBasenames = new Set(repos.map(repo => path.basename(repo)));
  const excludedNames = new Set(exclude.filter(value => repoBasenames.has(value)));
  const protect = [...ALWAYS_PROTECTED, ...exclude.filter(value => !repoBasenames.has(value))];

  for (const repo of repos) {
    const label = path.relative(cwd, repo) || '.';
    if (excludedNames.has(path.basename(repo))) {
      console.log(`${label}: skipped (--exclude)`);
      continue;
    }

    const lines = await cleanRepo(repo, { dryRun, protect });
    if (lines.length === 0) {
      console.log(`${label}: nothing to clean`);
      continue;
    }
    console.log(`${label}:`);
    for (const line of lines) console.log(`  ${line}`);
  }
};
