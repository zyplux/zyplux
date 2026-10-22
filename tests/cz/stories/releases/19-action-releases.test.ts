import { describe, expect, test } from './releases.ts';

test.override('targets', ({ actionRelease }) => actionRelease.targets);

describe('19.1 publishing versioned action releases', () => {
  test('19.1.1 creates reviewed release notes before advancing the major alias', async ({
    cz,
    releaseNotes,
    shell,
  }) => {
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    releaseNotes.capture();

    await cz.run('publish-tagged-target', '--release', 'setup-pm-v1.0.0');

    expect(releaseNotes.read()).toBe('- Cache package managers.\n');
    expect(shell.commandsMatching('gh release create')[0]).toContain('setup-pm-v1.0.0');
    expect(shell.commandsMatching('git push')).toEqual([
      'git push --force-with-lease=refs/tags/v1:old-sha origin release-sha:refs/tags/v1',
    ]);
    expect(shell).not.toHaveRunMatching(/pnpm pack|pnpm publish|uv build|uv publish/);
    const publication = shell.calls.findIndex(call => call.program === 'gh' && call.argv[0] === 'release');
    const promotion = shell.calls.findIndex(call => call.program === 'git' && call.argv[0] === 'push');
    expect(publication).toBeLessThan(promotion);
  });

  test('19.1.2 repairs a missing alias when the fixed release already exists', async ({ cz, shell }) => {
    shell.on('git ls-remote origin refs/tags/v1', '');

    await cz.run('publish-tagged-target', '--release', 'setup-pm-v1.0.0');

    expect(shell).not.toHaveRunMatching('gh release create');
    expect(shell.commandsMatching('git push')).toEqual([
      'git push --force-with-lease=refs/tags/v1: origin release-sha:refs/tags/v1',
    ]);
  });

  test('19.1.3 leaves a completed release unchanged', async ({ cz, shell }) => {
    shell.on('git ls-remote origin refs/tags/v1', 'release-sha\trefs/tags/v1');

    await cz.run('publish-tagged-target', '--release', 'setup-pm-v1.0.0');
    await cz.run('release-bumped-targets', '--list');

    expect(shell).not.toHaveRunMatching(/gh release create|git fetch|git push/);
  });

  test('19.1.4 retries an older release using the newest stable release in its major across all pages', async ({
    actionRelease,
    cz,
    shell,
  }) => {
    actionRelease.setPublished(
      ['setup-pm-v1.0.0', 'setup-pm-v2.0.0', 'cz-v99.0.0'],
      [
        'setup-pm-v1.9.0',
        'setup-pm-v1.10.0',
        { draft: true, tag: 'setup-pm-v1.11.0' },
        { prerelease: true, tag: 'setup-pm-v1.12.0' },
        'setup-pm-v1.13.0-beta.1',
        'setup-pm-vinvalid',
      ],
    );
    shell.on('git ls-remote origin refs/tags/setup-pm-v1.10.0*', 'newer-sha\trefs/tags/setup-pm-v1.10.0');
    shell.on('git rev-parse FETCH_HEAD^{commit}', 'newer-sha');

    await cz.run('publish-tagged-target', '--release', 'setup-pm-v1.0.0');

    expect(shell.commandsMatching('git fetch')).toEqual(['git fetch --no-tags origin refs/tags/setup-pm-v1.10.0']);
    expect(shell.commandsMatching('git push')).toEqual([
      'git push --force-with-lease=refs/tags/v1:old-sha origin newer-sha:refs/tags/v1',
    ]);
  });

  test('19.1.5 selects incomplete action releases for workflow retries', async ({ cz, logs, shell }) => {
    await cz.run('release-bumped-targets', '--list');
    expect(logs.logLines.at(-1)).toBe('[{"kind":"action","tag":"setup-pm-v1.0.0"}]');

    shell.on('git ls-remote origin refs/tags/v1', 'release-sha\trefs/tags/v1');
    await cz.run('release-bumped-targets', '--list');
    expect(logs.logLines.at(-1)).toBe('[]');
  });

  test('19.1.6 promotes the commit behind an annotated versioned tag', async ({ cz, shell }) => {
    shell.on(
      'git ls-remote origin refs/tags/setup-pm-v1.0.0*',
      'tag-object\trefs/tags/setup-pm-v1.0.0\nrelease-sha\trefs/tags/setup-pm-v1.0.0^{}',
    );

    await cz.run('publish-tagged-target', 'setup-pm-v1.0.0');

    expect(shell.commandsMatching('git push')[0]).toContain('origin release-sha:refs/tags/v1');
  });
});

describe('19.2 rejecting incomplete or racing publications', () => {
  test.for([
    { releases: [], shape: 'missing' },
    { releases: [{ draft: true, tag: 'setup-pm-v1.0.0' }], shape: 'draft' },
    { releases: [{ prerelease: true, tag: 'setup-pm-v1.0.0' }], shape: 'prerelease' },
  ])(
    '19.2.1 requires a published stable release before moving its alias (%j)',
    async ({ releases }, { actionRelease, cz, shell }) => {
      actionRelease.setPublished(releases);

      await expect(cz.run('publish-tagged-target', 'setup-pm-v1.0.0')).rejects.toThrow('before updating its major tag');
      expect(shell).not.toHaveRunMatching(/git fetch|git push/);
    },
  );

  test('19.2.2 leaves the alias unchanged when GitHub release creation fails', async ({ cz, shell }) => {
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    shell.on('gh release create', { exitCode: 1, stdout: '' });

    await expect(cz.run('publish-tagged-target', '--release', 'setup-pm-v1.0.0')).rejects.toThrow('exit code 1');
    expect(shell).not.toHaveRunMatching(/git fetch|git push/);
  });

  test('19.2.3 reports a rejected tag lease instead of forcing over a concurrent publisher', async ({ cz, shell }) => {
    shell.on('git push', { exitCode: 1, stdout: '' });

    await expect(cz.run('publish-tagged-target', 'setup-pm-v1.0.0')).rejects.toThrow('exit code 1');
    expect(shell.commandsMatching('git push')).toHaveLength(1);
    expect(shell.commandsMatching('git push')[0]).toContain('--force-with-lease=refs/tags/v1:old-sha');
  });

  test('19.2.4 refuses to publish a floating alias to a changed versioned tag', async ({ cz, shell }) => {
    shell.on('git rev-parse FETCH_HEAD^{commit}', 'changed-sha');

    await expect(cz.run('publish-tagged-target', 'setup-pm-v1.0.0')).rejects.toThrow('changed during publication');
    expect(shell).not.toHaveRunMatching('git push');
  });

  test('19.2.5 rejects invalid action versions before creating a release', async ({ cz, shell, tempDir }) => {
    await tempDir.write('apps/setup-pm/pyproject.toml', 'version = "1.0.0-beta.1"\n');

    await expect(cz.run('publish-tagged-target', 'setup-pm-v1.0.0-beta.1')).rejects.toThrow('must be stable semver');
    expect(shell).not.toHaveRunMatching(/gh release create|git push/);
  });

  test('19.2.6 rejects a missing versioned tag instead of guessing the current commit', async ({ cz, shell }) => {
    shell.on('git ls-remote origin refs/tags/setup-pm-v1.0.0*', '');

    await expect(cz.run('publish-tagged-target', 'setup-pm-v1.0.0')).rejects.toThrow(
      'published action tag setup-pm-v1.0.0 is missing',
    );
    expect(shell).not.toHaveRunMatching('git push');
  });
});

describe('19.3 preparing action versions through Changesets', () => {
  test('19.3.1 synchronizes the private manifest, native helper and lockfiles without a PyPI target', async ({
    actionRelease,
    cz,
    loadArtifact,
    prepareWorkspace,
    tempDir,
  }) => {
    await prepareWorkspace();
    await tempDir.write('pyproject.toml', '[tool.uv.workspace]\nmembers = ["apps/cerberus", "apps/setup-pm"]\n');
    await tempDir.write(
      'apps/setup-pm/pyproject.toml',
      '[project]\nname = "zyplux-setup-pm"\nversion = "1.0.0"\nrequires-python = ">=3.14"\n',
    );
    await tempDir.write(
      '.changeset/action.md',
      '---\n"zyplux-setup-pm": patch\n---\n\nCache compatible package-manager releases.\n',
    );

    await cz.run('prepare-release');
    await cz.run('check-release-notes');

    expect(await actionRelease.loadVersion()).toBe('1.0.1');
    expect(await loadArtifact('apps/setup-pm/pyproject.toml')).toContain('version = "1.0.1"');
    expect(await loadArtifact('apps/setup-pm/CHANGELOG.md')).toContain('Cache compatible package-manager releases.');
    expect(await loadArtifact('pnpm-lock.yaml')).toContain('apps/setup-pm');
    expect(await loadArtifact('uv.lock')).toContain('version = "1.0.1"');
    expect(tempDir.exists('.changeset/action.md')).toBe(false);
  });
});
