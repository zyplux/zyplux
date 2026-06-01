import { $ } from './shell-harness';
import { ensure, poll } from './util';

const ready = process.argv.includes('--ready') || process.argv.includes('-r');

const push = async () => {
  const branch = await $.git.currentBranch();
  ensure(branch.length > 0, 'not on any branch (detached HEAD?)');
  ensure(branch !== 'main', 'refusing to run on main');

  const existing = await $.gh.pr.state(branch);
  if (existing === 'MERGED') {
    console.log(`PR merged; switching to main and deleting local branch '${branch}'`);
    await $.git.checkout('main');
    await $.git.pull();
    await $.git.deleteBranch(branch);
    return;
  }

  await $.git.push('origin', branch);

  if (existing !== 'OPEN') {
    await $.gh.pr.create('main', branch);
  }
  if (ready && (await $.gh.pr.isDraft())) {
    await $.gh.pr.ready();
  }

  const url = await $.gh.pr.url();
  if (!ready) {
    console.log(`PR (draft): ${url}`);
    return;
  }

  const mergeState =
    (await poll(
      async () => {
        const state = await $.gh.pr.mergeState();
        return state === 'UNKNOWN' ? undefined : state;
      },
      10,
      1000,
    )) ?? 'UNKNOWN';
  ensure(mergeState !== 'UNKNOWN', 'merge state stayed UNKNOWN; check the PR on GitHub');
  ensure(mergeState !== 'DIRTY', 'merge conflict with main — rebase or resolve, then retry');

  if (mergeState === 'CLEAN') {
    await $.gh.pr.merge();
    console.log(`PR merged: ${url}`);
  } else {
    await $.gh.pr.mergeAuto();
    console.log(`PR ready, auto-merge scheduled (${mergeState}): ${url}`);
  }
};

try {
  await push();
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
