import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { command, constant } from '@optique/core/primitives';
import { ensure, poll } from '@zyplux/util';
import { $, readTrimmed } from '@zyplux/util/shell';

import { loadReleaseTargets } from '#release-targets';

export const releaseCommand = command(
  'release',
  object({
    command: constant('release' as const),
  }),
  {
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
  const knownRuns = splitLines(
    await readTrimmed(
      $.gh.run.list({ event: 'release', jq: '.[].databaseId', json: 'databaseId', workflow: 'release.yml' }),
    ),
  );
  await $.gh.release.create(target.tag, { generateNotes: true, target: remoteHead, title: target.tag });

  console.log('Watching the publish workflow ...');
  const headRunsQuery = `[.[] | select(.headSha=="${remoteHead}")] | .[].databaseId`;
  const runId = await poll(
    async () => {
      const ids = splitLines(
        await readTrimmed(
          $.gh.run.list({ event: 'release', jq: headRunsQuery, json: 'databaseId,headSha', workflow: 'release.yml' }),
        ),
      );
      return ids.find(id => !knownRuns.includes(id));
    },
    { attempts: 30, intervalMs: 2000 },
  );
  if (runId === undefined) {
    throw new Error('publish workflow did not start; check the Actions tab');
  }
  await $.gh.run.watch(runId, { exitStatus: true });

  console.log(`Verifying ${target.label} ${target.version} ...`);
  const visible = await poll(async () => ((await target.isPublished()) ? true : undefined), {
    attempts: 10,
    intervalMs: 3000,
  });
  ensure(visible === true, `${target.label} ${target.version} is not visible on its registry yet`);
  console.log(`Published ${target.label} ${target.version}`);
};

export const runRelease = async () => {
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

  for (const target of pending) {
    await publish(target, remoteHead);
  }
};
