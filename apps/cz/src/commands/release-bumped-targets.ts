import { ensure } from '@zyplux/util/assert';
import { poll } from '@zyplux/util/poll';
import { $, readTrimmed } from '@zyplux/util/shell';

import { command, constant, message, object } from '#optique';
import { loadReleaseTargets } from '#release-targets';

export const releaseBumpedTargetsCommand = command(
  'release-bumped-targets',
  object({
    command: constant('release-bumped-targets' as const),
  }),
  {
    aliases: ['r', 'release'],
    brief: message`Publish unpublished configured versions (npm, PyPI, GHCR) that have no GitHub release.`,
  },
);

type Target = {
  isPublished: () => Promise<boolean>;
  label: string;
  tag: string;
  version: string;
};

const listReleaseWorkflowRuns = async (tag: string) =>
  $.gh.run.list({ branch: tag, event: 'release', json: ['databaseId'], workflow: 'release.yml' });

const buildTargets = async () => {
  const targets = await loadReleaseTargets();
  return Promise.all(
    targets.map(async target => {
      const version = await target.readVersion();
      return {
        isPublished: async () => target.isPublished(version),
        label: target.label,
        tag: `${target.tagPrefix}${version}`,
        version,
      };
    }),
  );
};

const publish = async ({ isPublished, label, tag, version }: Target, remoteHead: string) => {
  console.log(`Creating GitHub release ${tag} ...`);
  const releaseRuns = await listReleaseWorkflowRuns(tag);
  const knownReleaseRuns = new Set(releaseRuns.map(({ databaseId }) => databaseId));
  await $.gh.release.create(tag, { generateNotes: true, target: remoteHead, title: tag });

  console.log(`Waiting for a new publish workflow run for ${tag} ...`);
  const releaseRunId = await poll(
    async () => {
      const newReleaseRuns = await listReleaseWorkflowRuns(tag);
      return newReleaseRuns.find(({ databaseId }) => !knownReleaseRuns.has(databaseId))?.databaseId;
    },
    {
      attempts: 12,
      intervalMs: 5000,
      onExpiry: 'publish workflow run was not found within the watch window; check the Actions tab',
    },
  );

  console.log(`Waiting for publish workflow run ${releaseRunId} to complete ...`);
  const { conclusion } = await poll(() => $.gh.run.view(releaseRunId, { json: ['status', 'conclusion'] }), {
    attempts: 60,
    intervalMs: 10_000,
    onExpiry: `publish workflow run ${releaseRunId} did not report completion within the watch window; check the Actions tab`,
    until: ({ status }) => status === 'completed',
  });
  ensure(
    conclusion === 'success',
    `publish workflow run ${releaseRunId} completed with conclusion '${conclusion === '' ? 'not reported' : conclusion}'`,
  );
  console.log(`Publish workflow run ${releaseRunId} succeeded`);

  console.log(`Checking registry availability for ${label} ${version} ...`);
  const visible = await poll(isPublished, { attempts: 12, intervalMs: 10_000, until: true });
  if (visible === true) {
    console.log(`Published ${label} ${version}`);
  } else {
    console.warn(
      `${label} ${version}: publish workflow succeeded, but registry availability was not confirmed within the watch window; check the registry and Actions tab`,
    );
  }
};

export const runReleaseBumpedTargets = async () => {
  const branch = await readTrimmed($.git.revParse('HEAD', { abbrevRef: true }));
  ensure(branch === 'main', `releases are cut from main, not '${branch}'`);

  const status = await readTrimmed($.git.status({ porcelain: true }));
  ensure(status.length === 0, 'working tree is dirty; commit or stash first');

  await $.git.fetch('origin', 'main');
  const head = await readTrimmed($.git.revParse('HEAD'));
  const remoteHead = await readTrimmed($.git.revParse('origin/main'));
  ensure(head === remoteHead, 'local main and origin/main differ; synchronize them before releasing');

  const pending: Target[] = [];
  const targets = await buildTargets();
  for (const target of targets) {
    if (await target.isPublished()) {
      console.log(`Skipping ${target.label} ${target.version} (already published)`);
    } else if (await $.gh.release.exists(target.tag)) {
      console.log(`Skipping ${target.label} ${target.version} (release ${target.tag} already exists)`);
    } else {
      pending.push(target);
    }
  }
  ensure(
    pending.length > 0,
    'nothing to release; all configured versions are already published or have a GitHub release',
  );

  const outcomes = await Promise.all(
    pending.map(async target => {
      try {
        await publish(target, remoteHead);
        return [];
      } catch (error) {
        return [{ reason: error instanceof Error ? error.message : String(error), target }];
      }
    }),
  );
  const failures = outcomes.flat();

  for (const { reason, target } of failures) {
    console.error(`${target.label} ${target.version}: ${reason}`);
  }
  ensure(
    failures.length === 0,
    `${failures.length} of ${pending.length} targets encountered release errors: ${failures.map(({ target }) => target.label).join(', ')}`,
  );
};
