import { ensure } from '@zyplux/util/assert';
import { $ } from '@zyplux/util/shell';

import type { ReleaseBatch } from './contracts.ts';
import type { ReleaseTarget } from './release-targets.ts';

import { isReleasePublished } from './github-releases.ts';
import { loadPreparedTargets } from './release-notes.ts';

export const buildReleaseBatches = (targets: ReleaseTarget[]): ReleaseBatch[] =>
  targets.map(target => ({
    environment: target.environment,
    id: `${target.kind}-${target.tagPrefix.replace(/-v$/u, '')}`,
    kind: target.kind,
    runner: 'ubuntu-latest',
    tags: [target.tag],
  }));

export const loadPendingTargets = async (tag?: string) => {
  const targets = await loadPreparedTargets();
  const selected = tag === undefined ? targets : targets.filter(target => target.tag === tag);
  ensure(tag === undefined || selected.length > 0, `no configured release target matches '${tag}'`);
  const pending = [];
  for (const target of selected) {
    const isPublished = await target.isPublished();
    const hasRelease =
      isPublished &&
      (target.artifactCommand !== undefined || target.assets.length > 0
        ? await isReleasePublished(target.tag, target.assets)
        : await $.gh.release.exists(target.tag));
    if (!hasRelease) pending.push(target);
  }
  return pending;
};
