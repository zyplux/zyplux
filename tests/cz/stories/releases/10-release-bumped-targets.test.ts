// unparametrized
import { describe, expect, test } from './releases.ts';

const START_ATTEMPTS = 12;
const COMPLETION_ATTEMPTS = 60;
const VISIBILITY_ATTEMPTS = 12;
const START_INTERVAL_MS = 5000;
const RELEASE_INTERVAL_MS = 10_000;

const renderRunViewCommand = (runId: string) => `gh run view ${runId} --json status,conclusion`;

describe('10. Releasing every target whose version was bumped', () => {
  describe('10.1 validating preconditions', () => {
    test('10.1.1 refuses to run anywhere but main', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow("releases are cut from main, not 'feat-x'");
      expect(shell).not.toHaveRunMatching('git status');
    });

    test('10.1.2 refuses to run with a dirty working tree', async ({ cz, repo, shell }) => {
      repo.syncMain('sha-head');
      repo.setWorkingTreeStatus(' M some-file.ts');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('working tree is dirty');
      expect(shell).not.toHaveRunMatching('git fetch');
    });

    test('10.1.3 refuses to run when local main is behind or ahead of origin/main', async ({ cz, repo }) => {
      repo.syncMain('sha-head');
      repo.setRemoteMainSha('sha-remote-ahead');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('local main and origin/main differ');
    });
  });

  describe('10.2 selecting which targets to release', () => {
    test('10.2.3 stops before creating releases when the release lookup fails', async ({ cz, release, shell }) => {
      release.stagePendingCerberus();
      shell.on('gh api graphql', { exitCode: 1, stdout: 'authentication failed' });
      await expect(cz.run('release-bumped-targets')).rejects.toMatchObject({ exitCode: 1 });
      expect(shell).not.toHaveRunMatching('gh release create');
    });

    test('10.2.1 skips a target whose version is already published', async ({ cz, logs, release, shell }) => {
      release.stageAllPublished();

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        'nothing to release; all configured versions are already published or have a GitHub release',
      );

      expect(logs).toHaveLogged('Skipping @zyplux/util 1.2.3 (already published)');
      expect(shell).not.toHaveRunMatching('gh release create');
    });

    test('10.2.2 skips a target that already has a github release', async ({ cz, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: false, pypiPublished: false });
      shell.on('gh api graphql', JSON.stringify({ data: { repository: { release: { id: 'release-id' } } } }));

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        'nothing to release; all configured versions are already published or have a GitHub release',
      );

      expect(logs).toHaveLogged('Skipping zyplux-cerberus 2.3.4 (release cerberus-v2.3.4 already exists)');
      expect(shell).not.toHaveRunMatching('gh release create');
    });
  });

  describe('10.3 publishing a pending target', () => {
    test('10.3.1 cuts a release, watches its workflow to success, and confirms registry visibility', async ({
      cz,
      logs,
      release,
      shell,
    }) => {
      release.stagePendingCerberus();
      release.queueRun('999', { conclusion: 'success', status: 'completed' });

      await cz.run('release-bumped-targets');

      expect(shell).toHaveRun(
        'gh release create cerberus-v2.3.4 --generate-notes --target sha-head --title cerberus-v2.3.4',
      );
      expect(shell).toHaveRun(renderRunViewCommand('999'));
      expect(logs).toHaveLogged('Published zyplux-cerberus 2.3.4');
    });

    test('10.3.2 rejects when the publish workflow finishes unsuccessfully, keeping the release and tag', async ({
      cz,
      logs,
      release,
      shell,
    }) => {
      release.stagePendingCerberus();
      release.queueRun('999', { conclusion: 'failure', status: 'completed' });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 1 targets encountered release errors: zyplux-cerberus',
      );
      expect(logs).toHaveErrored(/publish workflow run 999 completed with conclusion 'failure'/);
      expect(logs).not.toHaveWarned();
      expect(shell).not.toHaveRunMatching('gh release delete');
    });

    test('10.3.3 rejects when no new publish workflow run is found within the watch window, keeping the release and tag', async ({
      cz,
      logs,
      release,
      shell,
      sleep,
    }) => {
      release.stagePendingCerberus({ tagRunPolls: [['100', '101']] });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 1 targets encountered release errors: zyplux-cerberus',
      );
      expect(logs).toHaveErrored(/publish workflow run was not found within the watch window; check the Actions tab/);
      expect(shell).not.toHaveRunMatching('gh run view');
      expect(shell).not.toHaveRunMatching('gh release delete');
      expect(sleep).toHaveBeenCalledTimes(START_ATTEMPTS - 1);
      expect(sleep).toHaveBeenLastCalledWith(START_INTERVAL_MS);
    });

    test('10.3.4 rejects when the publish workflow does not report completion within the watch window, keeping the release and tag', async ({
      cz,
      logs,
      release,
      shell,
      sleep,
    }) => {
      release.stagePendingCerberus();
      release.queueRun('999', { status: 'in_progress' });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 1 targets encountered release errors: zyplux-cerberus',
      );
      expect(logs).toHaveErrored(
        /publish workflow run 999 did not report completion within the watch window; check the Actions tab/,
      );
      expect(shell).not.toHaveRunMatching('gh release delete');
      expect(sleep).toHaveBeenCalledTimes(COMPLETION_ATTEMPTS - 1);
      expect(sleep).toHaveBeenLastCalledWith(RELEASE_INTERVAL_MS);
    });

    test('10.3.5 warns instead of failing when registry checks do not confirm the new version within the watch window', async ({
      cz,
      logs,
      release,
      shell,
      sleep,
    }) => {
      release.stagePendingCerberus({ published: { pypiEverVisible: false } });
      release.queueRun('999', { conclusion: 'success', status: 'completed' });

      await cz.run('release-bumped-targets');

      expect(logs).toHaveWarned(
        'zyplux-cerberus 2.3.4: publish workflow succeeded, but registry availability was not confirmed within the watch window; check the registry and Actions tab',
      );
      expect(logs).not.toHaveLogged(/Published zyplux-cerberus/);
      expect(shell).not.toHaveRunMatching('gh release delete');
      expect(sleep).toHaveBeenCalledTimes(VISIBILITY_ATTEMPTS - 1);
      expect(sleep).toHaveBeenLastCalledWith(RELEASE_INTERVAL_MS);
    });

    test('10.3.6 keeps polling while the run list is still empty instead of watching a phantom run', async ({
      cz,
      logs,
      release,
      shell,
    }) => {
      release.stagePendingCerberus({ tagRunPolls: [[], ['100', '101', '999']] });
      release.queueRun('999', { conclusion: 'success', status: 'completed' });

      await cz.run('release-bumped-targets');

      expect(shell).toHaveRun(renderRunViewCommand('999'));
      expect(logs).toHaveLogged('Published zyplux-cerberus 2.3.4');
    });

    test('10.3.7 rejects when the workflow completes without reporting a conclusion, keeping the release and tag', async ({
      cz,
      logs,
      release,
      shell,
      sleep,
    }) => {
      release.stagePendingCerberus();
      release.queueRun('999', { conclusion: '', status: 'completed' });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 1 targets encountered release errors: zyplux-cerberus',
      );
      expect(logs).toHaveErrored(/publish workflow run 999 completed with conclusion 'not reported'/);
      expect(shell).not.toHaveRunMatching('gh release delete');
      expect(sleep).not.toHaveBeenCalled();
    });

    test('10.3.8 reports a workflow read error once while keeping the release and tag', async ({
      cz,
      logs,
      release,
      shell,
    }) => {
      release.stagePendingCerberus();
      shell.on('gh run view 999', () => {
        throw new Error('gh: connection reset');
      });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 1 targets encountered release errors: zyplux-cerberus',
      );
      expect(logs.errorLines).toEqual(['zyplux-cerberus 2.3.4: gh: connection reset']);
      expect(shell).not.toHaveRunMatching('gh release delete');
    });

    test('10.3.9 waits for completed status and checks the conclusion from the same response', async ({
      cz,
      logs,
      release,
      shell,
      sleep,
    }) => {
      release.stagePendingCerberus();
      const pendingPolls = 2;
      const runCommand = renderRunViewCommand('999');
      release.queueRun(
        '999',
        { status: 'queued' },
        { conclusion: 'failure', status: 'in_progress' },
        { conclusion: 'success', status: 'completed' },
      );

      await cz.run('release-bumped-targets');

      expect(shell.commandsMatching('gh run view')).toEqual([runCommand, runCommand, runCommand]);
      expect(sleep).toHaveBeenCalledTimes(pendingPolls);
      expect(sleep).toHaveBeenLastCalledWith(RELEASE_INTERVAL_MS);
      expect(logs).toHaveLogged('Published zyplux-cerberus 2.3.4');
    });
  });

  describe('10.4 publishing multiple pending targets', () => {
    test('10.4.1 publishes all pending targets concurrently, each watching its own tagged workflow run', async ({
      cz,
      logs,
      release,
      shell,
    }) => {
      release.stagePendingCerberusAndCiImage();
      release.completeRunAfter('111', '222', 'success');

      await cz.run('release-bumped-targets');

      const releaseCreateCommands = shell.commandsMatching('gh release create');
      expect(releaseCreateCommands).toContainEqual(expect.stringContaining('cerberus-v2.3.4'));
      expect(releaseCreateCommands).toContainEqual(expect.stringContaining('ci-image-v3.4.5'));
      expect(shell).toHaveRun(renderRunViewCommand('111'));
      expect(shell).toHaveRun(renderRunViewCommand('222'));
      expect(logs).toHaveLogged('Published zyplux-cerberus 2.3.4');
      expect(logs).toHaveLogged('Published ghcr.io/zyplux/ci 3.4.5');
    });

    test('10.4.2 keeps publishing the remaining targets when one fails and reports the failure at the end', async ({
      cz,
      logs,
      release,
    }) => {
      release.stagePendingCerberusAndCiImage();
      release.queueRun('111', { conclusion: 'failure', status: 'completed' });
      release.queueRun('222', { conclusion: 'success', status: 'completed' });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '1 of 2 targets encountered release errors: zyplux-cerberus',
      );

      expect(logs).toHaveLogged('Published ghcr.io/zyplux/ci 3.4.5');
      expect(logs).toHaveErrored("zyplux-cerberus 2.3.4: publish workflow run 111 completed with conclusion 'failure'");
    });

    test('10.4.3 reports failures in manifest order even when a later target fails first', async ({ cz, release }) => {
      release.stagePendingCerberusAndCiImage();
      release.completeRunAfter('111', '222', 'failure');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow(
        '2 of 2 targets encountered release errors: zyplux-cerberus, ghcr.io/zyplux/ci',
      );
    });
  });
});
