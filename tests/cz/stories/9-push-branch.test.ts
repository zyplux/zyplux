import { runPushBranch } from '@zyplux/cz/commands/push-branch';
import { fakeShellOutput } from '@zyplux/tests-shell-fixtures';
import { $ } from '@zyplux/util/shell';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@zyplux/util/shell', () => ({
  $: {
    gh: {
      api: vi.fn(),
      pr: {
        create: vi.fn(),
        disableAutoMerge: vi.fn(),
        list: vi.fn(),
        merge: vi.fn(),
        ready: vi.fn(),
        view: vi.fn(),
      },
      repo: { view: vi.fn() },
    },
    git: {
      branch: vi.fn(),
      checkout: vi.fn(),
      lsRemote: vi.fn(),
      pull: vi.fn(),
      push: vi.fn(),
      revParse: vi.fn(),
    },
  },
  readTrimmed: async (command: Promise<{ text: () => string }>) => {
    const output = await command;
    return output.text().trim();
  },
}));

const git = vi.mocked($.git, true);
const gh = vi.mocked($.gh, true);

const text = (value: string) => fakeShellOutput(value);

const SECOND_READY_CALL = 2;

describe('9. Pushing a branch and advancing its draft PR', () => {
  let branchName: string;
  let localHeadSha: string;
  const fieldQueues = new Map<string, string[]>();

  const queueField = (json: string, ...values: string[]) => {
    fieldQueues.set(json, [...values]);
  };

  const shiftField = (json: string | undefined) => {
    const value = json === undefined ? undefined : fieldQueues.get(json)?.shift();
    if (value === undefined) throw new Error(`unexpected gh.pr.view call for json=${json}`);
    return value;
  };

  const originalSleep = Bun.sleep;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, 'log').mockReturnValue(undefined);
    fieldQueues.clear();
    branchName = 'feat-x';
    localHeadSha = 'sha-local';
    Bun.sleep = () => Promise.resolve();

    git.revParse.mockImplementation((_rev, flags) =>
      Promise.resolve(text(flags?.abbrevRef ? branchName : localHeadSha)),
    );
    gh.pr.view.mockImplementation(({ json } = {}) => Promise.resolve(text(shiftField(json))));
  });

  afterEach(() => {
    Bun.sleep = originalSleep;
  });

  describe('9.1 validating preconditions', () => {
    it('9.1.1 rejects --hold without --ready', async () => {
      await expect(runPushBranch({ command: 'push-branch', hold: true, ready: false })).rejects.toThrow(
        '--hold requires --ready',
      );
      expect(git.revParse).not.toHaveBeenCalled();
    });

    it('9.1.2 rejects a detached HEAD', async () => {
      branchName = '';

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: false })).rejects.toThrow(
        'not on any branch',
      );
    });

    it('9.1.3 refuses to run on main', async () => {
      branchName = 'main';

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: false })).rejects.toThrow(
        'refusing to run on main',
      );
    });
  });

  describe('9.2 cleaning up after a merged PR', () => {
    it('9.2.1 switches to main and deletes the local branch once its PR is merged', async () => {
      gh.pr.list.mockResolvedValueOnce(text('MERGED'));

      await runPushBranch({ command: 'push-branch', hold: false, ready: false });

      expect(git.checkout).toHaveBeenCalledWith('main');
      expect(git.pull).toHaveBeenCalledWith({ ffOnly: true });
      expect(git.branch).toHaveBeenCalledWith('feat-x', { delete: true, force: true });
      expect(git.push).not.toHaveBeenCalled();
    });
  });

  describe('9.3 pushing and opening a new draft PR', () => {
    it('9.3.1 pushes the branch and opens a draft PR when none exists yet', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: false, ready: false });

      expect(git.push).toHaveBeenCalledWith('origin', 'feat-x', { setUpstream: true });
      expect(gh.pr.create).toHaveBeenCalledWith({ base: 'main', body: '', draft: true, title: 'feat-x' });
      expect(log).toHaveBeenCalledWith('PR (draft): https://github.com/zyplux/zyplux/pull/1');
      expect(gh.pr.ready).not.toHaveBeenCalled();
    });

    it('9.3.2 rejects a push that does not land on the expected head', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-elsewhere\trefs/heads/feat-x'));

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: false })).rejects.toThrow(
        'push did not land',
      );
      expect(gh.pr.create).not.toHaveBeenCalled();
    });
  });

  describe('9.4 flipping an already-ready PR to draft before pushing', () => {
    it('9.4.1 rejects the flip when nothing new to push and Copilot has not reviewed HEAD', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      gh.repo.view.mockResolvedValueOnce(text('zyplux/zyplux'));
      queueField('isDraft', 'false');
      queueField('number', '7');
      gh.api.mockResolvedValueOnce(text('sha-different'));

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: true })).rejects.toThrow(
        'Copilot has not reviewed HEAD',
      );
      expect(gh.pr.ready).not.toHaveBeenCalled();
      expect(git.push).not.toHaveBeenCalled();
    });

    it('9.4.2 flips to draft and pushes when Copilot already reviewed HEAD', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      gh.repo.view.mockResolvedValueOnce(text('zyplux/zyplux'));
      queueField('isDraft', 'false', 'true', 'false');
      queueField('number', '7');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'CLEAN');
      gh.api.mockResolvedValueOnce(text('sha-local'));
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: false, ready: true });

      expect(gh.pr.ready).toHaveBeenNthCalledWith(1, { undo: true });
      expect(log).toHaveBeenCalledWith('flip: GitHub confirms PR is draft (was ready, HEAD sha-loc)');
      expect(git.push).toHaveBeenCalledWith('origin', 'feat-x', { setUpstream: true });
      expect(gh.pr.ready).toHaveBeenNthCalledWith(SECOND_READY_CALL);
      expect(log).toHaveBeenCalledWith(
        'flip: GitHub confirms PR is ready (draft→push→ready done; Copilot re-review triggered)',
      );
      expect(gh.pr.merge).toHaveBeenCalledWith({ deleteBranch: true, squash: true });
    });

    it('9.4.3 skips the Copilot check when there are new commits to push', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-remote-old\trefs/heads/feat-x'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'false', 'true', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'CLEAN');

      await runPushBranch({ command: 'push-branch', hold: false, ready: true });

      expect(gh.repo.view).not.toHaveBeenCalled();
      expect(gh.api).not.toHaveBeenCalled();
      expect(gh.pr.ready).toHaveBeenNthCalledWith(1, { undo: true });
    });

    it('9.4.4 rejects when the PR never reports draft state', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-remote-old\trefs/heads/feat-x'));
      queueField('isDraft', 'false', ...Array.from({ length: 10 }, () => 'false'));

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: true })).rejects.toThrow(
        'PR did not enter draft state before push',
      );
      expect(git.push).not.toHaveBeenCalled();
    });
  });

  describe('9.5 flipping a draft PR back to ready', () => {
    it('9.5.1 flips an existing draft PR to ready after pushing', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'true', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'CLEAN');
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: false, ready: true });

      expect(gh.pr.ready).toHaveBeenCalledTimes(1);
      expect(gh.pr.ready).toHaveBeenNthCalledWith(1);
      expect(log).toHaveBeenCalledWith('flip: GitHub confirms PR is ready');
      expect(gh.pr.merge).toHaveBeenCalledWith({ deleteBranch: true, squash: true });
      expect(log).toHaveBeenCalledWith('PR merged: https://github.com/zyplux/zyplux/pull/1');
    });

    it('9.5.2 holds auto-merge when --hold is set', async () => {
      gh.pr.list.mockResolvedValueOnce(text('OPEN'));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'true', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: true, ready: true });

      expect(gh.pr.disableAutoMerge).toHaveBeenCalledTimes(1);
      expect(log).toHaveBeenCalledWith('PR ready, auto-merge held: https://github.com/zyplux/zyplux/pull/1');
      expect(gh.pr.merge).not.toHaveBeenCalled();
    });

    it('9.5.3 rejects when the PR never returns to ready state', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('isDraft', ...Array.from({ length: 10 }, () => 'true'));

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: true })).rejects.toThrow(
        'PR did not return to ready state; check the PR on GitHub',
      );
      expect(gh.pr.merge).not.toHaveBeenCalled();
    });
  });

  describe('9.6 merging a ready PR', () => {
    it('9.6.1 merges immediately when the merge state is clean', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'CLEAN');
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: false, ready: true });

      expect(gh.pr.merge).toHaveBeenCalledWith({ deleteBranch: true, squash: true });
      expect(log).toHaveBeenCalledWith('PR merged: https://github.com/zyplux/zyplux/pull/1');
    });

    it('9.6.2 rejects a dirty merge state', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'DIRTY');

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: true })).rejects.toThrow(
        'merge conflict',
      );
      expect(gh.pr.merge).not.toHaveBeenCalled();
    });

    it('9.6.3 schedules auto-merge for any other mergeable state', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', 'BEHIND');
      const log = vi.spyOn(console, 'log');

      await runPushBranch({ command: 'push-branch', hold: false, ready: true });

      expect(gh.pr.merge).toHaveBeenCalledWith({ auto: true, deleteBranch: true, squash: true });
      expect(log).toHaveBeenCalledWith(
        'PR ready, auto-merge scheduled (BEHIND): https://github.com/zyplux/zyplux/pull/1',
      );
    });

    it('9.6.4 rejects when the merge state stays UNKNOWN', async () => {
      gh.pr.list.mockResolvedValueOnce(text(''));
      git.lsRemote.mockResolvedValueOnce(text('sha-local\trefs/heads/feat-x'));
      queueField('isDraft', 'false');
      queueField('url', 'https://github.com/zyplux/zyplux/pull/1');
      queueField('mergeStateStatus', ...Array.from({ length: 10 }, () => 'UNKNOWN'));

      await expect(runPushBranch({ command: 'push-branch', hold: false, ready: true })).rejects.toThrow(
        'merge state stayed UNKNOWN; check the PR on GitHub',
      );
      expect(gh.pr.merge).not.toHaveBeenCalled();
    });
  });
});
