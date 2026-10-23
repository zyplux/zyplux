import { ensure } from '@zyplux/util/assert';
import { $ } from '@zyplux/util/shell';

import type { ReleaseBatch } from './contracts.ts';
import type { ReleaseTarget } from './release-targets.ts';

import { isReleasePublished } from './github-releases.ts';
import { loadPreparedTargets } from './release-notes.ts';

export const buildReleaseBatches = (targets: ReleaseTarget[]): ReleaseBatch[] => {
  const npm = targets.filter(target => target.kind === 'npm');
  const environment = npm[0]?.environment ?? 'npm';
  ensure(
    npm.every(target => target.environment === environment),
    'npm targets must share one environment to preserve dependency-ordered publication',
  );
  const batches: ReleaseBatch[] =
    npm.length === 0
      ? []
      : [
          {
            environment,
            id: 'npm',
            kind: 'npm',
            runner: 'ubuntu-latest',
            tags: npm.map(target => target.tag),
          },
        ];
  const otherBatches: ReleaseBatch[] = targets
    .filter(target => target.kind !== 'npm')
    .map(target => ({
      environment: target.environment,
      id: `${target.kind}-${target.tagPrefix.replace(/-v$/u, '')}`,
      kind: target.kind,
      runner: 'ubuntu-latest',
      tags: [target.tag],
    }));
  return [...batches, ...otherBatches];
};

export const loadPendingTargets = async (tag?: string) => {
  const targets = await loadPreparedTargets();
  const selected = tag === undefined ? targets : targets.filter(target => target.tag === tag);
  ensure(tag === undefined || selected.length > 0, `no configured release target matches '${tag}'`);
  const pending = [];
  for (const target of selected) {
    const isPublished = await target.isPublished();
    const hasRelease =
      isPublished &&
      (target.assets.length === 0
        ? await $.gh.release.exists(target.tag)
        : await isReleasePublished(target.tag, target.assets));
    if (!hasRelease) pending.push(target);
  }
  return pending;
};
