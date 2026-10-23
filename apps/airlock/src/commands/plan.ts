import type { InferValue } from '@optique/core';

import { command, constant, message, object, option, optional, string } from '@optique/core';
import { appendFile } from 'node:fs/promises';

import { buildReleaseBatches, loadPendingTargets } from '#release-batches';

const tagOption = optional(option('--tag', string({ metavar: 'TAG' })));

export const planCommand = command(
  'plan',
  object({
    command: constant('plan' as const),
    tag: tagOption,
  }),
  { brief: message`Select pending releases and expose publication batches to GitHub Actions.` },
);

type PlanConfig = InferValue<typeof planCommand>;

export const runPlan = async ({ tag }: PlanConfig) => {
  const matrix = { include: buildReleaseBatches(await loadPendingTargets(tag)) };
  console.log(JSON.stringify(matrix));
  const destination = process.env['GITHUB_OUTPUT'];
  if (destination === undefined) return;
  await appendFile(destination, `matrix=${JSON.stringify(matrix)}\npending=${matrix.include.length > 0}\n`);
};
