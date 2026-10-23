import { describe, expect, test } from './releases.ts';

describe('20.1 native npm publication', () => {
  test('20.1.1 repairs missing GitHub releases without republishing existing versions', async ({
    airlock,
    expectGithubRelease,
    registries,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    registries.setPublished({ npmPublished: true });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish-npm');

    expect(shell).not.toHaveRunMatching(/pnpm pack|pnpm publish/);
    await expectGithubRelease(shell, 'util-v1.2.3', 'sha-head');
  });

  test('20.1.2 propagates publication failure and permits a successful retry', async ({
    airlock,
    registries,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    registries.setPublished({ npmPublished: false });
    shell.on('pnpm publish', { exitCode: 1, stdout: 'registry visibility timed out' }, () => {
      registries.setPublished({ npmPublished: true });
      return '';
    });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await expect(airlock.run('publish-npm')).rejects.toThrow('command failed');
    expect(shell).not.toHaveRunMatching('gh release create');

    await airlock.run('publish-npm');

    expect(shell).toHaveRunMatching('gh release create util-v1.2.3');
  });

  test.for([
    { manifest: { name: '@zyplux/renamed', version: '1.2.3' }, reason: 'workspace package name' },
    { manifest: { name: '@zyplux/util', private: true, version: '1.2.3' }, reason: 'private workspace packages' },
  ])(
    '20.1.3 rejects mismatched or private workspace targets before publishing (%j)',
    async ({ manifest, reason }, { airlock, shell, tempDir }) => {
      await tempDir.write('packages/util/package.json', JSON.stringify(manifest));

      await expect(airlock.run('publish-npm')).rejects.toThrow(reason);

      expect(shell).not.toHaveRunMatching(/pnpm publish|gh release/);
    },
  );

  test('20.1.4 rejects targets excluded from the workspace before publishing', async ({ airlock, shell }) => {
    shell.on('pnpm list', '[]');

    await expect(airlock.run('publish-npm')).rejects.toThrow('is not a pnpm workspace package');

    expect(shell).not.toHaveRunMatching(/pnpm publish|gh release/);
  });

  test('20.1.5 requires the requested version in the registry before creating a GitHub release', async ({
    airlock,
    registries,
    shell,
  }) => {
    registries.setPublished({ npmPublished: false });
    shell.on('pnpm publish', '');

    await expect(airlock.run('publish-npm')).rejects.toThrow(
      'npm dependencies did not become available: @zyplux/util@1.2.3',
    );

    expect(shell).toHaveRunMatching('pnpm publish');
    expect(shell).not.toHaveRunMatching('gh release');
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
    shell.on(
      'gh api graphql',
      '{"data":{"repository":{"release":{"id":"published","isDraft":false,"releaseAssets":{"nodes":[{"name":"release.json"}]}}}}}',
    );

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
      shell.on(
        'gh api graphql',
        '{"data":{"repository":{"release":{"id":"published","isDraft":false,"releaseAssets":{"nodes":[{"name":"release.json"}]}}}}}',
      );

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
