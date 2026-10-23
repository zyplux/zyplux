import type { InferValue } from '@optique/core';

import { command, constant, message, object, option, optional, string } from '@optique/core';
import { appendFile } from 'node:fs/promises';

import { loadPreparedReleases } from '#release-notes';

import { listPendingTargets } from './release-bumped-targets.ts';

const tagOption = optional(option('--tag', string({ metavar: 'TAG' })));

export const planCommand = command(
  'plan',
  object({
    command: constant('plan' as const),
    tag: tagOption,
  }),
  { brief: message`Select pending releases and expose their matrices to GitHub Actions.` },
);

type PlanConfig = InferValue<typeof planCommand>;

export const runPlan = async ({ tag }: PlanConfig) => {
  await loadPreparedReleases();
  const pending = await listPendingTargets(tag);
  console.log(JSON.stringify(pending));
  const destination = process.env['GITHUB_OUTPUT'];
  if (destination === undefined) return;
  const outputs = ['npm', 'pypi', 'ghcr', 'action'].map(
    kind => `${kind}=${JSON.stringify(pending.filter(target => target.kind === kind).map(target => target.tag))}`,
  );
  await appendFile(destination, `${outputs.join('\n')}\n`);
};
