import { $, ensure, poll, readTrimmed } from '@zyplux/util';

import type { InferValue } from '#optique';

import { command, constant, message, object, option } from '#optique';

export const pushBranchCommand = command(
  'push-branch',
  object({
    command: constant('push-branch' as const),
    hold: option('--hold', {
      description: message`With --ready, re-trigger the Copilot review but hold off auto-merge; the caller decides when to merge.`,
    }),
    ready: option('-r', '--ready', {
      description: message`Flip the PR to draft, push, then mark it ready and enable auto-merge. New commits re-trigger Copilot review; with nothing to push it refreshes the gate (re-count resolved threads), provided Copilot already reviewed HEAD.`,
    }),
  }),
  {
    aliases: ['p'],
    brief: message`Push the current branch and open or advance its draft PR.`,
  },
);

type PushBranchConfig = InferValue<typeof pushBranchCommand>;

const SHORT_SHA_LENGTH = 7;
const shortSha = (sha: string) => sha.slice(0, SHORT_SHA_LENGTH);

const readRemoteHead = async (branch: string) => {
  const refLine = await readTrimmed($.git.lsRemote('origin', `refs/heads/${branch}`));
  return refLine.split(/\s+/, 1)[0] ?? '';
};

const readCopilotReviewedHead = async (slug: string, number: number) => {
  // This workflow has at most ten reviews per PR, so one page is sufficient.
  const reviews = await $.gh.pr.reviews(slug, number);
  return reviews.findLast(review => review.user?.login.toLowerCase().includes('copilot'))?.commit_id;
};

export const runPushBranch = async ({ hold, ready }: PushBranchConfig) => {
  ensure(!hold || ready, '--hold requires --ready');

  const branch = await readTrimmed($.git.revParse('HEAD', { abbrevRef: true }));
  ensure(branch.length > 0, 'not on any branch (detached HEAD?)');
  ensure(branch !== 'main', 'refusing to run on main');

  const [pr] = await $.gh.pr.list({ head: branch, json: ['state'], state: 'all' });
  const existing = pr?.state;
  if (existing === 'MERGED') {
    console.log(`PR merged; switching to main and deleting local branch '${branch}'`);
    await $.git.checkout('main');
    await $.git.pull({ ffOnly: true });
    await $.git.branch(branch, { delete: true, force: true });
    return;
  }

  const localHead = await readTrimmed($.git.revParse('HEAD'));
  const currentPr = ready && existing === 'OPEN' ? await $.gh.pr.view({ json: ['isDraft'] }) : undefined;
  const willFlipToDraft = currentPr?.isDraft === false;
  if (willFlipToDraft) {
    const remoteHead = await readRemoteHead(branch);
    if (remoteHead === localHead) {
      const { nameWithOwner } = await $.gh.repo.view({ json: ['nameWithOwner'] });
      const { number } = await $.gh.pr.view({ json: ['number'] });
      const reviewedHead = await readCopilotReviewedHead(nameWithOwner, number);
      ensure(
        reviewedHead === localHead,
        'nothing to push and Copilot has not reviewed HEAD: a draft→ready flip would re-trigger neither Copilot nor a useful gate run. Commit your fix and let this command push it during the cycle — do not pre-push the branch.',
      );
    }
    await $.gh.pr.ready({ undo: true });
    await poll(() => $.gh.pr.view({ json: ['isDraft'] }), {
      onExpiry:
        'PR did not enter draft state before push; aborting so the push is not seen on a ready PR (Copilot needs flip→push→flip)',
      until: ({ isDraft }) => isDraft,
    });
    console.log(`flip: GitHub confirms PR is draft (was ready, HEAD ${shortSha(localHead)})`);
  }

  await $.git.push('origin', branch, { setUpstream: true });
  const pushedHead = await readRemoteHead(branch);
  ensure(
    pushedHead === localHead,
    `push did not land: origin/${branch} is at ${shortSha(pushedHead)}, not ${shortSha(localHead)}`,
  );
  console.log(`push: GitHub confirms origin/${branch} is at ${shortSha(pushedHead)}`);

  if (existing !== 'OPEN') {
    await $.gh.pr.create({ base: 'main', body: '', draft: true, title: branch });
  }

  const { url } = await $.gh.pr.view({ json: ['url'] });
  if (!ready) {
    console.log(`PR (draft): ${url}`);
    return;
  }

  await $.gh.pr.ready();
  await poll(() => $.gh.pr.view({ json: ['isDraft'] }), {
    onExpiry: 'PR did not return to ready state; check the PR on GitHub',
    until: ({ isDraft }) => !isDraft,
  });
  console.log(
    `flip: GitHub confirms PR is ready${willFlipToDraft ? ' (draft→push→ready done; Copilot re-review triggered)' : ''}`,
  );

  if (hold) {
    await $.gh.pr.disableAutoMerge();
    console.log(`PR ready, auto-merge held: ${url}`);
    return;
  }

  const { mergeStateStatus } = await poll(() => $.gh.pr.view({ json: ['mergeStateStatus'] }), {
    attempts: 10,
    onExpiry: 'merge state stayed UNKNOWN; check the PR on GitHub',
    while: pr => pr.mergeStateStatus === 'UNKNOWN',
  });
  ensure(mergeStateStatus !== 'DIRTY', 'merge conflict with main — rebase or resolve, then retry');

  if (mergeStateStatus === 'CLEAN') {
    await $.gh.pr.merge({ deleteBranch: true, squash: true });
    console.log(`PR merged: ${url}`);
  } else {
    await $.gh.pr.merge({ auto: true, deleteBranch: true, squash: true });
    console.log(`PR ready, auto-merge scheduled (${mergeStateStatus}): ${url}`);
  }
};
