import { describe, expect, test } from './releases.ts';

describe('20.1 native npm publication', () => {
  test('20.1.1 filters declared targets and repairs missing GitHub releases', async ({
    airlock,
    expectGithubRelease,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    shell.on('pnpm --filter', '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish-npm');

    expect(shell).toHaveRun(
      'pnpm --filter @zyplux/util publish --recursive --report-summary --publish-wait-timeout 600000',
    );
    await expectGithubRelease(shell, 'util-v1.2.3', 'sha-head');
    expect(shell).not.toHaveRunMatching('pnpm pack');
  });

  test('20.1.2 propagates publication failure and permits a successful retry', async ({ airlock, repo, shell }) => {
    repo.syncMain('sha-head');
    shell.on('pnpm --filter', { exitCode: 1, stdout: 'registry visibility timed out' }, '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await expect(airlock.run('publish-npm')).rejects.toThrow('command failed');
    expect(shell).not.toHaveRunMatching('gh release create');

    await airlock.run('publish-npm');

    expect(shell).toHaveRunMatching('gh release create util-v1.2.3');
  });
});

describe('20.2 shared action release plans', () => {
  test('20.2.1 writes pending matrices to GitHub outputs', async ({
    airlock,
    loadActionOutputs,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
    shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"published"}}}}');

    await airlock.run('plan');

    expect(await loadActionOutputs()).toBe(
      `matrix=${JSON.stringify({
        include: [
          {
            environment: 'pypi',
            id: 'pypi-cerberus',
            kind: 'pypi',
            runner: 'ubuntu-latest',
            tags: ['cerberus-v2.3.4'],
          },
        ],
      })}\npending=true\n`,
    );
  });

  test.for([
    { files: [], shouldPublish: true },
    { files: ['bdist_wheel'], shouldPublish: true },
    { files: ['sdist'], shouldPublish: true },
    { files: ['bdist_wheel', 'sdist'], shouldPublish: false },
  ])(
    '20.2.2 keeps incomplete PyPI releases pending even when their GitHub release exists (%j)',
    async ({ files, shouldPublish }, { airlock, loadActionOutputs, network, shell }) => {
      network.on('https://pypi.org/', () => Response.json({ urls: files.map(packagetype => ({ packagetype })) }));
      shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"published"}}}}');

      await airlock.run('plan', '--tag', 'cerberus-v2.3.4');

      expect(await loadActionOutputs()).toBe(
        `matrix=${JSON.stringify({
          include: shouldPublish
            ? [
                {
                  environment: 'pypi',
                  id: 'pypi-cerberus',
                  kind: 'pypi',
                  runner: 'ubuntu-latest',
                  tags: ['cerberus-v2.3.4'],
                },
              ]
            : [],
        })}\npending=${shouldPublish}\n`,
      );
    },
  );
});

describe('20.4 recovering PyPI publication', () => {
  test('20.4.1 retries a partial upload before creating its GitHub release', async ({
    airlock,
    network,
    repo,
    shell,
  }) => {
    repo.syncMain('reviewed-sha');
    network.on('https://pypi.org/', () => Response.json({ urls: [{ packagetype: 'bdist_wheel' }] }));
    shell.on('uv build', '');
    shell.on('uv publish', { exitCode: 1, stdout: 'Upload interrupted.' }, '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await expect(airlock.run('publish-tagged-target', '--release', 'cerberus-v2.3.4')).rejects.toThrow(
      'command failed',
    );
    expect(shell).not.toHaveRunMatching('gh release create');

    await airlock.run('publish-tagged-target', '--release', 'cerberus-v2.3.4');

    const publicationAttempts = 2;
    expect(shell.commandsMatching('uv publish')).toHaveLength(publicationAttempts);
    expect(shell).toHaveRunMatching('gh release create cerberus-v2.3.4');
  });

  test.for([
    { metadata: {}, status: 200 },
    { metadata: { urls: [{}] }, status: 200 },
    { metadata: {}, status: 403 },
    { metadata: {}, status: 502 },
  ])(
    '20.4.2 stops before building or creating a release when PyPI metadata is invalid (%j)',
    async ({ metadata, status }, { airlock, network, shell }) => {
      network.on('https://pypi.org/', () => Response.json(metadata, { status }));

      await expect(airlock.run('publish-tagged-target', '--release', 'cerberus-v2.3.4')).rejects.toThrow();

      expect(shell).not.toHaveRunMatching(/uv|gh release create/);
    },
  );
});

describe('20.3 prebuilt container release assets', () => {
  test('20.3.1 uploads assets to a draft before publishing the release', async ({
    airlock,
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

    await airlock.run('publish-tagged-target', '--release', 'ci-image-v3.4.5', '--asset', releaseAssetPath);

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
    async ({ error, isDraft, uploads }, { airlock, registries, releaseAssetPath, repo, shell, tempDir }) => {
      repo.syncMain('sha-head');
      registries.setPublished({ ghcrPublished: true });
      await tempDir.write('release.json', '{}');
      shell.on(
        'gh api graphql',
        JSON.stringify({ data: { repository: { release: { isDraft, releaseAssets: { nodes: [] } } } } }),
      );
      shell.on('gh release upload', { exitCode: 1, stdout: 'upload failed' });

      await expect(
        airlock.run('publish-tagged-target', '--release', 'ci-image-v3.4.5', '--asset', releaseAssetPath),
      ).rejects.toThrow(error);

      expect(shell.commandsMatching('gh release upload')).toHaveLength(uploads);
      expect(shell).not.toHaveRunMatching(/gh release create|gh release edit/);
    },
  );
});
