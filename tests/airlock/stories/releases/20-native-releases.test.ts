import { describe, expect, test } from './releases.ts';

describe('20.1 native npm publication', () => {
  test('20.1.1 filters declared targets and repairs missing GitHub releases', async ({
    expectGithubRelease,
    nativeRelease,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    shell.on('pnpm --filter', '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await nativeRelease.run('publish-npm');

    expect(shell).toHaveRun(
      'pnpm --filter @zyplux/util publish --recursive --report-summary --publish-wait-timeout 600000',
    );
    await expectGithubRelease(shell, 'util-v1.2.3', 'sha-head');
    expect(shell).not.toHaveRunMatching('pnpm pack');
  });

  test('20.1.2 propagates publication failure and permits a successful retry', async ({
    nativeRelease,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    shell.on('pnpm --filter', { exitCode: 1, stdout: 'registry visibility timed out' }, '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await expect(nativeRelease.run('publish-npm')).rejects.toThrow('command failed');
    expect(shell).not.toHaveRunMatching('gh release create');

    await nativeRelease.run('publish-npm');

    expect(shell).toHaveRunMatching('gh release create util-v1.2.3');
  });
});

describe('20.2 shared action release plans', () => {
  test('20.2.1 writes pending matrices to GitHub outputs', async ({
    loadActionOutputs,
    nativeRelease,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
    shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"published"}}}}');

    await nativeRelease.run('plan');

    expect(await loadActionOutputs()).toBe('npm=[]\npypi=["cerberus-v2.3.4"]\nghcr=[]\naction=[]\n');
  });
});

describe('20.3 prebuilt container release assets', () => {
  test('20.3.1 uploads assets to a draft before publishing the release', async ({
    nativeRelease,
    registries,
    releaseAssetPath,
    repo,
    shell,
    tempDir,
  }) => {
    repo.syncMain('sha-head');
    registries.setPublished({ ghcrPublished: true });
    await tempDir.write('release.json', '{"image":"ghcr.io/zyplux/ci@sha256:example"}');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    shell.on('gh release upload', '');
    shell.on('gh release edit', '');

    await nativeRelease.run('publish', '--release', 'ci-image-v3.4.5', '--asset', releaseAssetPath);

    const [create, upload, publish] = shell.commandsMatching('gh release');
    expect(create).toContain('create ci-image-v3.4.5 --draft');
    expect(upload).toContain('upload ci-image-v3.4.5');
    expect(publish).toContain('edit ci-image-v3.4.5 --draft=false');
    expect(shell).not.toHaveRunMatching('podman');
  });

  test.for([
    { error: 'command failed', isDraft: true, uploads: 1 },
    { error: 'missing required assets', isDraft: false, uploads: 0 },
  ])(
    '20.3.2 rejects incomplete release assets (%j)',
    async ({ error, isDraft, uploads }, { nativeRelease, registries, releaseAssetPath, repo, shell, tempDir }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true });
      await tempDir.write('release.json', '{}');
      shell.on(
        'gh api graphql',
        JSON.stringify({ data: { repository: { release: { isDraft, releaseAssets: { nodes: [] } } } } }),
      );
      shell.on('gh release upload', { exitCode: 1, stdout: 'upload failed' });

      await expect(
        nativeRelease.run('publish', '--release', 'ci-image-v3.4.5', '--asset', releaseAssetPath),
      ).rejects.toThrow(error);

      expect(shell.commandsMatching('gh release upload')).toHaveLength(uploads);
      expect(shell).not.toHaveRunMatching(/gh release create|gh release edit/);
    },
  );
});
