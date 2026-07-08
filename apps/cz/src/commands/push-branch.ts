import type { InferValue } from '@optique/core/parser';

import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { command, constant, option } from '@optique/core/primitives';
import { $, ensure, poll, readTrimmed } from '@zyplux/util';

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

const readPrField = async (json: string, jq: string) => readTrimmed($.gh.pr.view({ jq, json }));

const readRemoteHead = async (branch: string) => {
  const refLine = await readTrimmed($.git.lsRemote('origin', `refs/heads/${branch}`));
  return refLine.split(/\s+/, 1)[0] ?? '';
};

const readCopilotReviewedHead = async (slug: string, number: string) =>
  readTrimmed(
    $.gh.api(`repos/${slug}/pulls/${number}/reviews?per_page=100`, {
      jq: '[.[] | select((.user.login // "") | ascii_downcase | contains("copilot"))] | last | .commit_id // ""',
    }),
  );

export const runPushBranch = async ({ hold, ready }: PushBranchConfig) => {
  ensure(!hold || ready, '--hold requires --ready');

  const branch = await readTrimmed($.git.revParse('HEAD', { abbrevRef: true }));
  ensure(branch.length > 0, 'not on any branch (detached HEAD?)');
  ensure(branch !== 'main', 'refusing to run on main');

  const existing = await readTrimmed(
    $.gh.pr.list({ head: branch, jq: '.[0].state // ""', json: 'state', state: 'all' }),
  );
  if (existing === 'MERGED') {
    console.log(`PR merged; switching to main and deleting local branch '${branch}'`);
    await $.git.checkout('main');
    await $.git.pull({ ffOnly: true });
    await $.git.branch(branch, { delete: true, force: true });
    return;
  }

  const localHead = await readTrimmed($.git.revParse('HEAD'));
  const willFlipToDraft = ready && existing === 'OPEN' && (await readPrField('isDraft', '.isDraft')) === 'false';
  if (willFlipToDraft) {
    const remoteHead = await readRemoteHead(branch);
    if (remoteHead === localHead) {
      const slug = await readTrimmed($.gh.repo.view({ jq: '.nameWithOwner', json: 'nameWithOwner' }));
      const number = await readPrField('number', '.number');
      const reviewedHead = await readCopilotReviewedHead(slug, number);
      ensure(
        reviewedHead === localHead,
        'nothing to push and Copilot has not reviewed HEAD: a draft→ready flip would re-trigger neither Copilot nor a useful gate run. Commit your fix and let this command push it during the cycle — do not pre-push the branch.',
      );
    }
    await $.gh.pr.ready({ undo: true });
    const draftApplied = await poll(
      async () => ((await readPrField('isDraft', '.isDraft')) === 'true' ? true : undefined),
      { attempts: 10, intervalMs: 500 },
    );
    ensure(
      draftApplied === true,
      'PR did not enter draft state before push; aborting so the push is not seen on a ready PR (Copilot needs flip→push→flip)',
    );
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

  const url = await readPrField('url', '.url');
  if (!ready) {
    console.log(`PR (draft): ${url}`);
    return;
  }

  await $.gh.pr.ready();
  const readyApplied = await poll(
    async () => ((await readPrField('isDraft', '.isDraft')) === 'false' ? true : undefined),
    { attempts: 10, intervalMs: 500 },
  );
  ensure(readyApplied === true, 'PR did not return to ready state; check the PR on GitHub');
  console.log(
    `flip: GitHub confirms PR is ready${willFlipToDraft ? ' (draft→push→ready done; Copilot re-review triggered)' : ''}`,
  );

  if (hold) {
    await $.gh.pr.disableAutoMerge();
    console.log(`PR ready, auto-merge held: ${url}`);
    return;
  }

  const mergeState =
    (await poll(
      async () => {
        const state = await readPrField('mergeStateStatus', '.mergeStateStatus');
        return state === 'UNKNOWN' ? undefined : state;
      },
      { attempts: 10, intervalMs: 1000 },
    )) ?? 'UNKNOWN';
  ensure(mergeState !== 'UNKNOWN', 'merge state stayed UNKNOWN; check the PR on GitHub');
  ensure(mergeState !== 'DIRTY', 'merge conflict with main — rebase or resolve, then retry');

  if (mergeState === 'CLEAN') {
    await $.gh.pr.merge({ deleteBranch: true, squash: true });
    console.log(`PR merged: ${url}`);
  } else {
    await $.gh.pr.merge({ auto: true, deleteBranch: true, squash: true });
    console.log(`PR ready, auto-merge scheduled (${mergeState}): ${url}`);
  }
};
