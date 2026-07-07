import { describe, expect, test } from '#fixtures';

const KNOWN_RUNS_PATTERN = /--json databaseId --workflow/;
const TAG_RUNS_PATTERN = /--json databaseId,headBranch/;

const renderRunViewCommand = (runId: string) => `gh run view ${runId} --jq .status, .conclusion --json status,conclusion`;

describe('10. Releasing every target whose version was bumped', () => {
  describe('10.1 validating preconditions', () => {
    test('10.1.1 refuses to run anywhere but main', async ({ cz, repo, shell }) => {
      repo.setCurrentBranch('feat-x');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow("releases are cut from main, not 'feat-x'");
      expect(shell.commandsMatching('git status')).toHaveLength(0);
    });

    test('10.1.2 refuses to run with a dirty working tree', async ({ cz, repo, shell }) => {
      repo.syncMain('sha-head');
      repo.setWorkingTreeStatus(' M some-file.ts');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('working tree is dirty');
      expect(shell.commandsMatching('git fetch')).toHaveLength(0);
    });

    test('10.1.3 refuses to run when local main is behind or ahead of origin/main', async ({ cz, repo }) => {
      repo.syncMain('sha-head');
      repo.setRemoteMainSha('sha-remote-ahead');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('local main and origin/main differ');
    });
  });

  describe('10.2 selecting which targets to release', () => {
    test('10.2.1 skips a target whose version is already published', async ({ cz, findTarget, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
      const util = await findTarget('@zyplux/util');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

      expect(logs.logLines).toContain(`Skipping @zyplux/util ${util.version} (already published)`);
      expect(shell.commandsMatching('gh release create')).toHaveLength(0);
    });

    test('10.2.2 skips a target that already has a github release', async ({ cz, findTarget, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: false, pypiPublished: false });
      shell.on('gh release list', 'true');
      const cerberus = await findTarget('zyplux-cerberus');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

      expect(logs.logLines).toContain(`Skipping zyplux-cerberus ${cerberus.version} (release cerberus-v${cerberus.version} already exists)`);
      expect(shell.commandsMatching('gh release create')).toHaveLength(0);
    });
  });

  describe('10.3 publishing a pending target', () => {
    test('10.3.1 cuts a release, watches its workflow to success, and confirms registry visibility', async ({
      cz,
      findTarget,
      logs,
      registries,
      repo,
      shell,
    }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101\n999');
      shell.on('gh run view 999', 'completed\nsuccess');
      const cerberus = await findTarget('zyplux-cerberus');

      await cz.run('release-bumped-targets');

      expect(shell.commands).toContain(
        `gh release create cerberus-v${cerberus.version} --generate-notes --target sha-head --title cerberus-v${cerberus.version}`,
      );
      expect(shell.commands).toContain(renderRunViewCommand('999'));
      expect(logs.logLines).toContain(`Published zyplux-cerberus ${cerberus.version}`);
    });

    test('10.3.2 rejects when the publish workflow finishes unsuccessfully', async ({ cz, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101\n999');
      shell.on('gh run view 999', 'completed\nfailure');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('1 of 1 targets failed to publish: zyplux-cerberus');
      expect(logs.errorLines).toContainEqual(expect.stringContaining("publish workflow 999 finished with 'failure'"));
      expect(logs.warnLines).toHaveLength(0);
    });

    test('10.3.3 rejects when the publish workflow never starts', async ({ cz, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('1 of 1 targets failed to publish: zyplux-cerberus');
      expect(logs.errorLines).toContainEqual(expect.stringContaining('publish workflow did not start; check the Actions tab'));
      expect(shell.commandsMatching('gh run view')).toHaveLength(0);
    });

    test('10.3.4 rejects when the publish workflow never completes', async ({ cz, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101\n999');
      shell.on('gh run view 999', 'in_progress');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('1 of 1 targets failed to publish: zyplux-cerberus');
      expect(logs.errorLines).toContainEqual(expect.stringContaining('publish workflow 999 did not complete within the watch window; check the Actions tab'));
    });

    test('10.3.5 warns instead of failing when the registry never shows the new version', async ({ cz, findTarget, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({
        ghcrPublished: true,
        npmPublished: true,
        pypiEverVisible: false,
        pypiPublished: false,
      });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101\n999');
      shell.on('gh run view 999', 'completed\nsuccess');
      const cerberus = await findTarget('zyplux-cerberus');

      await cz.run('release-bumped-targets');

      expect(logs.warnLines).toContain(
        `zyplux-cerberus ${cerberus.version} published (workflow succeeded) but is not visible on its registry yet — likely propagation lag; it should appear shortly`,
      );
      expect(logs.logLines).not.toContainEqual(expect.stringContaining('Published zyplux-cerberus'));
    });

    test('10.3.6 keeps polling while the run list is still empty instead of watching a phantom run', async ({
      cz,
      findTarget,
      logs,
      registries,
      repo,
      shell,
    }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '', '100\n101\n999');
      shell.on('gh run view 999', 'completed\nsuccess');
      const cerberus = await findTarget('zyplux-cerberus');

      await cz.run('release-bumped-targets');

      expect(shell.commands).toContain(renderRunViewCommand('999'));
      expect(logs.logLines).toContain(`Published zyplux-cerberus ${cerberus.version}`);
    });

    test('10.3.7 rejects when the workflow completes without reporting a conclusion', async ({ cz, logs, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100\n101');
      shell.on(TAG_RUNS_PATTERN, '100\n101\n999');
      shell.on('gh run view 999', 'completed');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('1 of 1 targets failed to publish: zyplux-cerberus');
      expect(logs.errorLines).toContainEqual(expect.stringContaining("publish workflow 999 finished with 'unknown'"));
    });
  });

  describe('10.4 publishing multiple pending targets', () => {
    test('10.4.1 publishes all pending targets concurrently, each watching its own tagged workflow run', async ({
      cz,
      findTarget,
      logs,
      registries,
      repo,
      shell,
    }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100');
      shell.on(/gh run list.*cerberus-v/, '100\n111');
      shell.on(/gh run list.*ci-image-v/, '100\n222');
      let isCiImageRunCompleted = false;
      shell.on('gh run view 111', () => (isCiImageRunCompleted ? 'completed\nsuccess' : 'in_progress'));
      shell.on('gh run view 222', () => {
        isCiImageRunCompleted = true;
        return 'completed\nsuccess';
      });
      const cerberus = await findTarget('zyplux-cerberus');
      const ciImage = await findTarget('ghcr.io/zyplux/ci');

      await cz.run('release-bumped-targets');

      const releaseCreateCommands = shell.commandsMatching('gh release create');
      expect(releaseCreateCommands).toContainEqual(expect.stringContaining(`cerberus-v${cerberus.version}`));
      expect(releaseCreateCommands).toContainEqual(expect.stringContaining(`ci-image-v${ciImage.version}`));
      expect(shell.commands).toContain(renderRunViewCommand('111'));
      expect(shell.commands).toContain(renderRunViewCommand('222'));
      expect(logs.logLines).toContain(`Published zyplux-cerberus ${cerberus.version}`);
      expect(logs.logLines).toContain(`Published ghcr.io/zyplux/ci ${ciImage.version}`);
    });

    test('10.4.2 keeps publishing the remaining targets when one fails and reports the failure at the end', async ({
      cz,
      findTarget,
      logs,
      registries,
      repo,
      shell,
    }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100');
      shell.on(/gh run list.*cerberus-v/, '100\n111');
      shell.on(/gh run list.*ci-image-v/, '100\n222');
      shell.on('gh run view 111', 'completed\nfailure');
      shell.on('gh run view 222', 'completed\nsuccess');
      const cerberus = await findTarget('zyplux-cerberus');
      const ciImage = await findTarget('ghcr.io/zyplux/ci');

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('1 of 2 targets failed to publish: zyplux-cerberus');

      expect(logs.logLines).toContain(`Published ghcr.io/zyplux/ci ${ciImage.version}`);
      expect(logs.errorLines).toContain(`zyplux-cerberus ${cerberus.version}: publish workflow 111 finished with 'failure'`);
    });

    test('10.4.3 reports failures in manifest order even when a later target fails first', async ({ cz, registries, repo, shell }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: false, npmPublished: true, pypiPublished: false });
      shell.on('gh release list', 'false');
      shell.on(KNOWN_RUNS_PATTERN, '100');
      shell.on(/gh run list.*cerberus-v/, '100\n111');
      shell.on(/gh run list.*ci-image-v/, '100\n222');
      let isCiImageRunCompleted = false;
      shell.on('gh run view 111', () => (isCiImageRunCompleted ? 'completed\nfailure' : 'in_progress'));
      shell.on('gh run view 222', () => {
        isCiImageRunCompleted = true;
        return 'completed\nfailure';
      });

      await expect(cz.run('release-bumped-targets')).rejects.toThrow('2 of 2 targets failed to publish: zyplux-cerberus, ghcr.io/zyplux/ci');
    });
  });
});
