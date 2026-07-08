import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { command, constant } from '@optique/core/primitives';
import { $, ensure, poll, readTrimmed } from '@zyplux/util';

import { loadReleaseTargets } from '#release-targets';

export const releaseBumpedTargetsCommand = command(
  'release-bumped-targets',
  object({
    command: constant('release-bumped-targets' as const),
  }),
  {
    aliases: ['r', 'release'],
    brief: message`Publish any bumped release target (npm, PyPI, GHCR) via a GitHub release.`,
  },
);

type Target = {
  isPublished: () => Promise<boolean>;
  label: string;
  tag: string;
  version: string;
};

const splitLines = (text: string) => (text ? text.split('\n') : []);

const listReleaseRunIds = async (jq: string, json = 'databaseId') =>
  splitLines(await readTrimmed($.gh.run.list({ event: 'release', jq, json, workflow: 'release.yml' })));

const releaseExists = async (tag: string) =>
  (await readTrimmed($.gh.release.list({ jq: `any(.[]; .tagName == "${tag}")`, json: 'tagName' }))) === 'true';

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

const publish = async (target: Target, remoteHead: string) => {
  console.log(`Cutting release ${target.tag} ...`);
  const knownRuns = await listReleaseRunIds('.[].databaseId');
  await $.gh.release.create(target.tag, { generateNotes: true, target: remoteHead, title: target.tag });

  console.log(`Watching the publish workflow for ${target.tag} ...`);
  const tagRunsQuery = `[.[] | select(.headBranch=="${target.tag}")] | .[].databaseId`;
  const runId = await poll(
    async () => {
      const ids = await listReleaseRunIds(tagRunsQuery, 'databaseId,headBranch');
      return ids.find(id => !knownRuns.includes(id));
    },
    { attempts: 30, intervalMs: 2000 },
  );
  if (runId === undefined) {
    throw new Error('publish workflow did not start; check the Actions tab');
  }

  console.log(`Watching run ${runId} ...`);
  const conclusion = await poll(
    async () => {
      const [status, result] = splitLines(
        await readTrimmed($.gh.run.view(runId, { jq: '.status, .conclusion', json: 'status,conclusion' })),
      );
      return status === 'completed' ? (result ?? '') : undefined;
    },
    { attempts: 200, intervalMs: 3000 },
  );
  if (conclusion === undefined) {
    throw new Error(`publish workflow ${runId} did not complete within the watch window; check the Actions tab`);
  }
  ensure(conclusion === 'success', `publish workflow ${runId} finished with '${conclusion || 'unknown'}'`);
  console.log(`Run ${runId} succeeded`);

  console.log(`Verifying ${target.label} ${target.version} ...`);
  const visible = await poll(async () => ((await target.isPublished()) ? true : undefined), {
    attempts: 20,
    intervalMs: 6000,
  });
  if (visible === true) {
    console.log(`Published ${target.label} ${target.version}`);
  } else {
    console.warn(
      `${target.label} ${target.version} published (workflow succeeded) but is not visible on its registry yet — likely propagation lag; it should appear shortly`,
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
  ensure(head === remoteHead, 'local main and origin/main differ; push or pull first');

  const pending: Target[] = [];
  const targets = await buildTargets();
  for (const target of targets) {
    if (await target.isPublished()) {
      console.log(`Skipping ${target.label} ${target.version} (already published)`);
    } else if (await releaseExists(target.tag)) {
      console.log(`Skipping ${target.label} ${target.version} (release ${target.tag} already exists)`);
    } else {
      pending.push(target);
    }
  }
  ensure(pending.length > 0, 'nothing to release; bump a version first');

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
    `${failures.length} of ${pending.length} targets failed to publish: ${failures.map(({ target }) => target.label).join(', ')}`,
  );
};
