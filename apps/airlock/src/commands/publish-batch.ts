import type { InferValue } from '@optique/core';

import { command, constant, message, object, option, string } from '@optique/core';
import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { appendFile } from 'node:fs/promises';
import { isDeepStrictEqual } from 'node:util';

import { ReleaseBatchSchema } from '#contracts';
import { buildReleaseBatches } from '#release-batches';
import { loadPreparedTargets } from '#release-notes';
import { loadReleaseTargets } from '#release-targets';

import { publishNpmTargets } from './publish-npm.ts';
import { publishPreparedTarget } from './publish-tagged-target.ts';

const batchOption = option('--batch', string({ metavar: 'JSON' }));

export const publishBatchCommand = command(
  'publish',
  object({
    batch: batchOption,
    command: constant('publish-batch' as const),
  }),
  { brief: message`Publish exactly one planned batch and finalize its GitHub releases.` },
);

export const runPublishBatch = async ({ batch: json }: InferValue<typeof publishBatchCommand>) => {
  const batch = parseJson(json, ReleaseBatchSchema);
  const targets = await loadReleaseTargets();
  const selected = batch.tags.map(tag => {
    const target = targets.find(target => target.tag === tag);
    ensure(target !== undefined, `no configured release target matches '${tag}'`);
    return target;
  });
  const [expected, ...others] = buildReleaseBatches(selected);
  ensure(
    others.length === 0 && isDeepStrictEqual(batch, expected),
    'batch does not match the configured publication group',
  );
  const releases = await loadPreparedTargets(selected);
  let hasPublished = false;
  try {
    if (batch.kind === 'npm') await publishNpmTargets(releases);
    else for (const target of releases) await publishPreparedTarget(target, target.notes, []);
    hasPublished = true;
  } finally {
    const summary = process.env['GITHUB_STEP_SUMMARY'];
    if (summary !== undefined)
      await appendFile(
        summary,
        `### ${batch.id}: ${hasPublished ? 'published' : 'failed'}\n\n${batch.tags.map(tag => `- ${tag}`).join('\n')}\n\n`,
      );
  }
};
