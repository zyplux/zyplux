import pkg from '../packages/eslint-config/package.json' with { type: 'json' };
import { $, ensure, poll } from './shell-harness';

const packageName = '@totvibe/eslint-config';
const { version } = pkg;
const tag = `v${version}`;
const spec = `${packageName}@${version}`;

const release = async () => {
  const branch = await $.git.currentBranch();
  ensure(branch === 'main', `releases are cut from main, not '${branch}'`);

  const status = await $.git.status();
  ensure(status.length === 0, 'working tree is dirty; commit or stash first');

  await $.git.fetch('origin', 'main');
  const head = await $.git.revParse('HEAD');
  const remoteHead = await $.git.revParse('origin/main');
  ensure(head === remoteHead, 'local main and origin/main differ; push or pull first');

  const released = await $.gh.release.view(tag);
  ensure(!released, `release ${tag} already exists`);

  console.log(`Cutting release ${tag} from main ...`);
  await $.gh.release.create(tag, { target: 'main' });

  console.log('Watching the publish workflow ...');
  const runId = await poll(
    () => $.gh.run.find({ event: 'release', headSha: remoteHead, workflow: 'release.yml' }),
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
      const info = await $.bun.pm.view(spec);
      return info.length > 0 ? spec : undefined;
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
