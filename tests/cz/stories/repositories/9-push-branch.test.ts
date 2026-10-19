// unparametrized
import { describe, expect, test } from './repositories.ts';

const PR_URL = 'https://github.com/zyplux/zyplux/pull/1';

const GATE_COMMAND = 'gh api repos/{owner}/{repo}/commits/sha-local/statuses';
const OLD_GATE = { context: 'bot-review-complete', id: 100, state: 'success' };
const NEW_GATE = { ...OLD_GATE, id: 101 };

describe('9. Pushing a branch and advancing its draft PR', () => {
  test.beforeEach(({ shell }) => {
    shell.on(GATE_COMMAND, JSON.stringify([OLD_GATE]), JSON.stringify([NEW_GATE, OLD_GATE]));
  });
  describe('9.1 validating preconditions', () => {
    test('9.1.1 rejects --hold without --ready', async ({ cz, shell }) => {
      await expect(cz.run('push-branch', '--hold')).rejects.toThrow('--hold requires --ready');
      expect(shell).not.toHaveRunMatching('git rev-parse');
    });

    test('9.1.2 rejects a detached HEAD', async ({ cz, repo }) => {
      repo.setCurrentBranch('');

      await expect(cz.run('push-branch')).rejects.toThrow('not on any branch');
    });

    test('9.1.3 refuses to run on main', async ({ cz, repo }) => {
      repo.setCurrentBranch('main');

      await expect(cz.run('push-branch')).rejects.toThrow('refusing to run on main');
    });
  });

  describe('9.2 cleaning up after a merged PR', () => {
    test('9.2.1 switches to main and deletes the local branch once its PR is merged', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setPrListState('MERGED');

      await cz.run('push-branch');

      expect(shell).toHaveRun('git checkout main');
      expect(shell).toHaveRun('git pull --ff-only');
      expect(shell).toHaveRun('git branch --delete --force feat-x');
      expect(shell).not.toHaveRunMatching('git push');
    });
  });

  describe('9.3 pushing and opening a new draft PR', () => {
    test('9.3.1 pushes the branch and opens a draft PR when none exists yet', async ({ cz, logs, repo, shell }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('');
      repo.queuePrFields({ url: PR_URL });

      await cz.run('push-branch');

      expect(shell).toHaveRun('git push --set-upstream origin feat-x');
      expect(shell.calls).toContainEqual({
        argv: ['pr', 'create', '--base', 'main', '--body', '', '--draft', '--title', 'feat-x'],
        program: 'gh',
      });
      expect(logs).toHaveLogged(`PR (draft): ${PR_URL}`);
      expect(shell).not.toHaveRunMatching('gh pr ready');
    });

    test('9.3.2 rejects a push that does not land on the expected head', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.setRemoteBranchSha('feat-x', 'sha-elsewhere');

      await expect(cz.run('push-branch')).rejects.toThrow('push did not land');
      expect(shell).not.toHaveRunMatching('gh pr create');
    });
  });

  describe('9.4 flipping an already-ready PR to draft before pushing', () => {
    test('9.4.1 refreshes an unchanged PR through its required checks', async ({ cz, logs, repo, shell }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrFields({
        isDraft: [false, true, false],
        mergeStateStatus: 'CLEAN',
        url: PR_URL,
      });

      await cz.run('push-branch', '--ready');

      expect(shell.commandsMatching('gh pr ready')).toEqual(['gh pr ready --undo', 'gh pr ready']);
      expect(logs).toHaveLogged('flip: GitHub confirms PR is draft (was ready, HEAD sha-loc)');
      expect(shell).toHaveRun('git push --set-upstream origin feat-x');
      expect(logs).toHaveLogged('flip: GitHub confirms PR is ready (draft→push→ready done)');
      expect(shell).toHaveRun('gh pr merge --delete-branch --match-head-commit sha-local --squash');
    });

    test('9.4.2 pushes between the draft and ready transitions', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrFields({ isDraft: [false, true, false], mergeStateStatus: 'CLEAN', url: PR_URL });
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell).not.toHaveRunMatching('gh repo view');
      expect(shell.commandsMatching(/gh pr ready|git push/u)).toEqual([
        'gh pr ready --undo',
        'git push --set-upstream origin feat-x',
        'gh pr ready',
      ]);
    });

    test('9.4.3 rejects when the PR never reports draft state', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrFields({ isDraft: false });
      repo.setRemoteBranchSha('feat-x', 'sha-remote-old');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('PR did not enter draft state before push');
      expect(shell).not.toHaveRunMatching('git push');
    });
  });

  describe('9.5 flipping a draft PR back to ready', () => {
    test('9.5.1 flips an existing draft PR to ready after pushing', async ({ cz, logs, repo, shell }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrFields({ isDraft: [true, false], mergeStateStatus: 'CLEAN', url: PR_URL });

      await cz.run('push-branch', '--ready');

      expect(shell.commandsMatching('gh pr ready')).toEqual(['gh pr ready']);
      expect(logs).toHaveLogged('flip: GitHub confirms PR is ready');
      expect(shell).toHaveRun('gh pr merge --delete-branch --match-head-commit sha-local --squash');
      expect(logs).toHaveLogged(`PR merged: ${PR_URL}`);
    });

    test('9.5.2 holds auto-merge when --hold is set', async ({ cz, logs, repo, shell }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrFields({ isDraft: [true, false], url: PR_URL });

      await cz.run('push-branch', '--hold', '--ready');

      expect(shell.commandsMatching('gh pr merge')).toEqual(['gh pr merge --disable-auto']);
      expect(logs).toHaveLogged(`PR ready, auto-merge held: ${PR_URL}`);
    });

    test('9.5.3 rejects when the PR never returns to ready state', async ({ cz, repo, shell }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('');
      repo.queuePrFields({ isDraft: true, url: PR_URL });

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow(
        'PR did not return to ready state; check the PR on GitHub',
      );
      expect(shell).not.toHaveRunMatching('gh pr merge');
    });
  });

  describe('9.6 merging a ready PR', () => {
    test.beforeEach(({ repo }) => {
      repo.syncFeatureBranch('feat-x', 'sha-local');
      repo.setPrListState('');
      repo.queuePrFields({ isDraft: false, mergeStateStatus: 'CLEAN', url: PR_URL });
    });

    test('9.6.1 merges the checked head after the refreshed gate succeeds', async ({ cz, logs, shell }) => {
      await cz.run('push-branch', '--ready');

      expect(shell).toHaveRun('gh pr merge --delete-branch --match-head-commit sha-local --squash');
      expect(logs).toHaveLogged(`PR merged: ${PR_URL}`);
    });

    test('9.6.2 rejects a dirty merge state', async ({ cz, repo, shell }) => {
      repo.queuePrFields({ isDraft: false, mergeStateStatus: 'DIRTY', url: PR_URL });

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('merge conflict');
      expect(shell).not.toHaveRunMatching('gh pr merge');
    });

    test('9.6.3 schedules auto-merge for any other mergeable state', async ({ cz, logs, repo, shell }) => {
      repo.queuePrFields({ isDraft: false, mergeStateStatus: 'BEHIND', url: PR_URL });

      await cz.run('push-branch', '--ready');

      expect(shell).toHaveRun('gh pr merge --auto --delete-branch --match-head-commit sha-local --squash');
      expect(logs).toHaveLogged(`PR ready, auto-merge scheduled (BEHIND): ${PR_URL}`);
    });

    test('9.6.4 rejects when the merge state stays UNKNOWN', async ({ cz, repo, shell, sleep }) => {
      repo.queuePrFields({ isDraft: false, mergeStateStatus: 'UNKNOWN', url: PR_URL });

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow(
        'merge state stayed UNKNOWN; check the PR on GitHub',
      );
      expect(shell).not.toHaveRunMatching('gh pr merge');
      const attempts = 10;
      const intervalMs = 1000;
      expect(sleep).toHaveBeenCalledTimes(attempts - 1);
      expect(sleep).toHaveBeenLastCalledWith(intervalMs);
    });

    test('9.6.5 waits for a fresh gate on the pushed head before merging an unchanged clean PR', async ({
      cz,
      repo,
      shell,
    }) => {
      repo.setPrListState('OPEN');
      repo.queuePrFields({ isDraft: [false, true, false], mergeStateStatus: 'CLEAN', url: PR_URL });
      shell.on(
        GATE_COMMAND,
        JSON.stringify([OLD_GATE]),
        JSON.stringify([OLD_GATE]),
        JSON.stringify([{ ...NEW_GATE, state: 'pending' }, OLD_GATE]),
        () => {
          expect(shell).not.toHaveRunMatching('gh pr merge');
          expect(shell).not.toHaveRunMatching('gh pr view --json mergeStateStatus');
          return JSON.stringify([NEW_GATE, OLD_GATE]);
        },
      );

      await cz.run('push-branch', '--ready');

      const gatePolls = 4;
      expect(shell.commandsMatching(GATE_COMMAND)).toHaveLength(gatePolls);
      expect(shell).toHaveRun('gh pr merge --delete-branch --match-head-commit sha-local --squash');
    });

    test('9.6.6 refuses to merge when the refreshed gate fails', async ({ cz, shell }) => {
      shell.on(GATE_COMMAND, JSON.stringify([OLD_GATE]), JSON.stringify([{ ...NEW_GATE, state: 'failure' }, OLD_GATE]));

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow("refreshed review gate concluded 'failure'");
      expect(shell).not.toHaveRunMatching('gh pr merge');
    });

    test('9.6.7 refuses to merge when no fresh gate appears', async ({ cz, shell }) => {
      shell.on(GATE_COMMAND, JSON.stringify([OLD_GATE]));

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('refreshed review gate did not complete');
      expect(shell).not.toHaveRunMatching('gh pr merge');
    });

    test('9.6.8 refuses to merge when the refreshed gate never completes', async ({ cz, shell }) => {
      shell.on(GATE_COMMAND, '[]', JSON.stringify([{ ...NEW_GATE, state: 'pending' }]));

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('refreshed review gate did not complete');
      expect(shell).not.toHaveRunMatching('gh pr merge');
    });
  });
});
