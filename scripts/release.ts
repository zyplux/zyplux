import pkg from '@zyplux/eslint-config/package.json' with { type: 'json' };

import { $ } from './shell-harness';
import { ensure, poll } from './util';

const packageName = '@zyplux/eslint-config';
const { version } = pkg;
const tag = `v${version}`;
const spec = `${packageName}@${version}`;
const registryUrl = `https://registry.npmjs.org/${packageName.replace('/', '%2f')}/${version}`;

const release = async () => {
  const branch = await $.git.currentBranch();
  ensure(branch === 'main', `releases are cut from main, not '${branch}'`);

  const status = await $.git.status();
  ensure(status.length === 0, 'working tree is dirty; commit or stash first');

  await $.git.fetch('origin', 'main');
  const head = await $.git.revParse('HEAD');
  const remoteHead = await $.git.revParse('origin/main');
  ensure(head === remoteHead, 'local main and origin/main differ; push or pull first');

  const exists = await $.gh.release.exists(tag);
  ensure(!exists, `release ${tag} already exists`);

  const knownRuns = await $.gh.run.ids({ event: 'release', workflow: 'release.yml' });

  console.log(`Cutting release ${tag} from main ...`);
  await $.gh.release.create(tag, { target: 'main' });

  console.log('Watching the publish workflow ...');
  const runId = await poll(
    () => $.gh.run.find({ event: 'release', headSha: remoteHead, knownIds: knownRuns, workflow: 'release.yml' }),
    30,
    2000,
  );
  if (runId === undefined) {
    throw new Error('publish workflow did not start; check the Actions tab');
  }
  await $.gh.run.watch(runId);

  console.log(`Verifying ${spec} on npm ...`);
  const published = await poll(
    async () => {
      const response = await fetch(registryUrl);
      return response.ok ? spec : undefined;
    },
    10,
    3000,
  );
  ensure(published !== undefined, `${spec} is not visible on npm yet`);
  console.log(`Published ${spec}`);
};

try {
  await release();
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
