import { describe, expect, test } from '#fixtures';

const PR_URL = 'https://github.com/zyplux/zyplux/pull/1';

describe('9. Pushing a branch and advancing its draft PR', () => {
  describe('9.1 validating preconditions', () => {
    test('9.1.1 rejects --hold without --ready', async ({ cz, shell }) => {
      await expect(cz.run('push-branch', '--hold')).rejects.toThrow('--hold requires --ready');
      expect(shell.commandsMatching('git rev-parse')).toHaveLength(0);
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

      expect(shell.commands).toContain('git checkout main');
      expect(shell.commands).toContain('git pull --ff-only');
      expect(shell.commands).toContain('git branch --delete --force feat-x');
      expect(shell.commandsMatching('git push')).toHaveLength(0);
    });
  });

  describe('9.3 pushing and opening a new draft PR', () => {
    test('9.3.1 pushes the branch and opens a draft PR when none exists yet', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.setRemoteBranchSha('feat-x', 'sha-local');
      repo.queuePrField('url', PR_URL);

      await cz.run('push-branch');

      expect(shell.commands).toContain('git push --set-upstream origin feat-x');
      expect(shell.calls).toContainEqual({
        argv: ['pr', 'create', '--base', 'main', '--body', '', '--draft', '--title', 'feat-x'],
        program: 'gh',
      });
      expect(logs.logLines).toContain(`PR (draft): ${PR_URL}`);
      expect(shell.commandsMatching('gh pr ready')).toHaveLength(0);
    });

    test('9.3.2 rejects a push that does not land on the expected head', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.setRemoteBranchSha('feat-x', 'sha-elsewhere');

      await expect(cz.run('push-branch')).rejects.toThrow('push did not land');
      expect(shell.commandsMatching('gh pr create')).toHaveLength(0);
    });
  });

  describe('9.4 flipping an already-ready PR to draft before pushing', () => {
    test('9.4.1 rejects the flip when nothing new to push and Copilot has not reviewed HEAD', async ({
      cz,
      repo,
      shell,
    }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'false');
      repo.queuePrField('number', '7');
      repo.setRemoteBranchSha('feat-x', 'sha-local');
      repo.setRepoSlug('zyplux/zyplux');
      repo.setCopilotReviewedHead('sha-different');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('Copilot has not reviewed HEAD');
      expect(shell.commandsMatching('gh pr ready')).toHaveLength(0);
      expect(shell.commandsMatching('git push')).toHaveLength(0);
    });

    test('9.4.2 flips to draft and pushes when Copilot already reviewed HEAD', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'false', 'true', 'false');
      repo.queuePrField('number', '7');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'CLEAN');
      repo.setRemoteBranchSha('feat-x', 'sha-local');
      repo.setRepoSlug('zyplux/zyplux');
      repo.setCopilotReviewedHead('sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell.commandsMatching('gh pr ready')).toEqual(['gh pr ready --undo', 'gh pr ready']);
      expect(logs.logLines).toContain('flip: GitHub confirms PR is draft (was ready, HEAD sha-loc)');
      expect(shell.commands).toContain('git push --set-upstream origin feat-x');
      expect(logs.logLines).toContain(
        'flip: GitHub confirms PR is ready (draft→push→ready done; Copilot re-review triggered)',
      );
      expect(shell.commands).toContain('gh pr merge --delete-branch --squash');
    });

    test('9.4.3 skips the Copilot check when there are new commits to push', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'false', 'true', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'CLEAN');
      repo.setRemoteBranchSha('feat-x', 'sha-remote-old', 'sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell.commandsMatching('gh repo view')).toHaveLength(0);
      expect(shell.commandsMatching('gh api')).toHaveLength(0);
      expect(shell.commandsMatching('gh pr ready')).toEqual(['gh pr ready --undo', 'gh pr ready']);
    });

    test('9.4.4 rejects when the PR never reports draft state', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'false');
      repo.setRemoteBranchSha('feat-x', 'sha-remote-old');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('PR did not enter draft state before push');
      expect(shell.commandsMatching('git push')).toHaveLength(0);
    });
  });

  describe('9.5 flipping a draft PR back to ready', () => {
    test('9.5.1 flips an existing draft PR to ready after pushing', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'true', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'CLEAN');
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell.commandsMatching('gh pr ready')).toEqual(['gh pr ready']);
      expect(logs.logLines).toContain('flip: GitHub confirms PR is ready');
      expect(shell.commands).toContain('gh pr merge --delete-branch --squash');
      expect(logs.logLines).toContain(`PR merged: ${PR_URL}`);
    });

    test('9.5.2 holds auto-merge when --hold is set', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('OPEN');
      repo.queuePrField('isDraft', 'true', 'false');
      repo.queuePrField('url', PR_URL);
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await cz.run('push-branch', '--hold', '--ready');

      expect(shell.commandsMatching('gh pr merge')).toEqual(['gh pr merge --disable-auto']);
      expect(logs.logLines).toContain(`PR ready, auto-merge held: ${PR_URL}`);
    });

    test('9.5.3 rejects when the PR never returns to ready state', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.queuePrField('isDraft', 'true');
      repo.queuePrField('url', PR_URL);
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow(
        'PR did not return to ready state; check the PR on GitHub',
      );
      expect(shell.commandsMatching('gh pr merge')).toHaveLength(0);
    });
  });

  describe('9.6 merging a ready PR', () => {
    test('9.6.1 merges immediately when the merge state is clean', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.queuePrField('isDraft', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'CLEAN');
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell.commands).toContain('gh pr merge --delete-branch --squash');
      expect(logs.logLines).toContain(`PR merged: ${PR_URL}`);
    });

    test('9.6.2 rejects a dirty merge state', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.queuePrField('isDraft', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'DIRTY');
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow('merge conflict');
      expect(shell.commandsMatching('gh pr merge')).toHaveLength(0);
    });

    test('9.6.3 schedules auto-merge for any other mergeable state', async ({ cz, logs, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.queuePrField('isDraft', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'BEHIND');
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await cz.run('push-branch', '--ready');

      expect(shell.commands).toContain('gh pr merge --auto --delete-branch --squash');
      expect(logs.logLines).toContain(`PR ready, auto-merge scheduled (BEHIND): ${PR_URL}`);
    });

    test('9.6.4 rejects when the merge state stays UNKNOWN', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');
      repo.setHeadSha('sha-local');
      repo.setPrListState('');
      repo.queuePrField('isDraft', 'false');
      repo.queuePrField('url', PR_URL);
      repo.queuePrField('mergeStateStatus', 'UNKNOWN');
      repo.setRemoteBranchSha('feat-x', 'sha-local');

      await expect(cz.run('push-branch', '--ready')).rejects.toThrow(
        'merge state stayed UNKNOWN; check the PR on GitHub',
      );
      expect(shell.commandsMatching('gh pr merge')).toHaveLength(0);
    });
  });
});
