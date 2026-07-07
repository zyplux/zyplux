import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { withDefault } from '@optique/core/modifiers';
import { command, constant, option } from '@optique/core/primitives';
import { string } from '@optique/core/valueparser';
import path from 'node:path';

import { collectDepRepos } from '#deps-catalog';

const JSON_INDENT = 2;

const dirOption = withDefault(
  option('--dir', string({ metavar: 'DIR' }), {
    description: message`Directory to scan for repos (defaults to the current directory).`,
  }),
  '.',
);

const outOption = withDefault(
  option('--out', string({ metavar: 'FILE' }), {
    description: message`Where to write the repo list (defaults to catalog.json in the scanned directory).`,
  }),
  'catalog.json',
);

export const depsCatalogCommand = command('deps-catalog', object({ command: constant('deps-catalog' as const), dir: dirOption, out: outOption }), {
  aliases: ['dc'],
  brief: message`Resolve every dependency across the repos to its source repository and write the list to JSON.`,
});

type DepsCatalogConfig = InferValue<typeof depsCatalogCommand>;

export const runDepsCatalog = async ({ dir, out }: DepsCatalogConfig) => {
  const { repos, unresolved } = await collectDepRepos(dir);
  const outPath = path.isAbsolute(out) ? out : path.join(dir, out);
  await Bun.write(outPath, `${JSON.stringify(repos, undefined, JSON_INDENT)}\n`);

  console.log(`Wrote ${repos.length} source repositories to ${outPath}`);
  if (unresolved.length > 0) {
    console.log(`Unresolved (${unresolved.length}) — no source repo found:`);
    for (const { name, system } of unresolved) console.log(`  ${system}\t${name}`);
  }
};
