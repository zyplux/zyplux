import { describe, expect, test } from './releases.ts';

const DIGEST_HEX_LENGTH = 64;
const RETRY_BUILD_COUNT = 2;

describe('22.1 publishing application-specific container artifacts', () => {
  test('22.1.1 runs the artifact command with the reviewed version and uploads its manifest before publication', async ({
    airlock,
    containerRelease,
    shell,
    tempDir,
  }) => {
    await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));
    expect(containerRelease.readManifest()).toBe(
      JSON.stringify({
        coreVersion: '3.4.5',
        image: `ghcr.io/zyplux/ci@sha256:${'1'.repeat(DIGEST_HEX_LENGTH)}`,
        revision: 'reviewed-sha',
        validatorVersion: '1.2.3',
      }),
    );
    const builder = shell.calls.find(call => call.program === 'uv');
    expect(builder?.argv).toEqual(['run', '--no-sync', 'python', '-m', 'vps_deployment.build_release']);
    expect(builder?.cwd).toBe(tempDir.path);
    expect(builder?.env?.['AIRLOCK_TAG']).toBe('ci-image-v3.4.5');
    expect(shell.commandsMatching('gh release')).toEqual([
      expect.stringContaining('create ci-image-v3.4.5 --draft'),
      expect.stringContaining('upload ci-image-v3.4.5'),
      expect.stringContaining('edit ci-image-v3.4.5 --draft=false'),
    ]);
    expect(shell).toHaveRun('podman logout ghcr.io');
  });

  test('22.1.2 rebuilds unfinished releases despite an existing image tag', async ({
    airlock,
    containerRelease,
    registries,
    repo,
    shell,
  }) => {
    shell.on('gh api graphql', '{"data":{"repository":{"release":{"isDraft":true,"releaseAssets":{"nodes":[]}}}}}');
    await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));
    registries.setPublished({ ghcrPublished: true });
    repo.setHeadSha('retry-sha');
    await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));
    expect(containerRelease.readManifest()).toContain(`sha256:${'2'.repeat(DIGEST_HEX_LENGTH)}`);
    expect(containerRelease.readManifest()).toContain('retry-sha');
    expect(shell.commandsMatching('uv run')).toHaveLength(RETRY_BUILD_COUNT);
  });

  test.for([
    { reason: 'command failed', reply: { exitCode: 1, stdout: 'build failed' } },
    { reason: 'ENOENT', reply: '' },
  ])(
    '22.1.3 keeps releases unpublished and removes credentials when artifact generation fails (%j)',
    async ({ reason, reply }, { airlock, containerRelease, shell }) => {
      shell.on('uv run', reply);
      await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(reason);
      expect(shell).not.toHaveRunMatching('gh release');
      expect(shell).toHaveRun('podman logout ghcr.io');
    },
  );

  test('22.1.4 preserves a finalized release and its manifest', async ({
    airlock,
    containerRelease,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true });
    shell.on(
      'gh api graphql',
      '{"data":{"repository":{"release":{"isDraft":false,"releaseAssets":{"nodes":[{"name":"release.json"}]}}}}}',
    );
    await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));
    expect(shell).not.toHaveRunMatching(/podman|uv run|gh release/);
  });

  test('22.1.5 rejects a finalized release whose image is missing without changing its manifest', async ({
    airlock,
    containerRelease,
    planReleases,
    shell,
  }) => {
    shell.on(
      'gh api graphql',
      '{"data":{"repository":{"release":{"isDraft":false,"releaseAssets":{"nodes":[{"name":"release.json"}]}}}}}',
    );
    expect(await planReleases(containerRelease.batch.tags[0])).toEqual([containerRelease.batch]);

    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      'published release ci-image-v3.4.5 is missing image ghcr.io/zyplux/ci:3.4.5',
    );

    expect(shell).not.toHaveRunMatching(/podman|uv run|gh release/);
  });

  test('22.1.6 rejects a custom builder that finishes without publishing its image', async ({
    airlock,
    configureTarget,
    containerRelease,
    shell,
  }) => {
    await configureTarget('ghcr', 'assets = []');
    shell.on('uv run', '');

    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      'artifact command did not publish image ghcr.io/zyplux/ci:3.4.5',
    );

    expect(shell).not.toHaveRunMatching('gh release');
    expect(shell).toHaveRun('podman logout ghcr.io');
  });

  test.for([false, true])(
    '22.1.7 publishes image-only custom releases and resumes drafts without uploading assets (%j)',
    async (isDraft, { airlock, configureTarget, containerRelease, planReleases, registries, shell }) => {
      await configureTarget('ghcr', 'assets = []');
      registries.setPublished({ ghcrPublished: true });
      shell.on(
        'gh api graphql',
        isDraft
          ? '{"data":{"repository":{"release":{"isDraft":true,"releaseAssets":{"nodes":[]}}}}}'
          : '{"data":{"repository":{"release":null}}}',
      );
      expect(await planReleases(containerRelease.batch.tags[0])).toEqual([containerRelease.batch]);

      await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));

      expect(shell).not.toHaveRunMatching('gh release upload');
      expect(shell).toHaveRunMatching('gh release edit ci-image-v3.4.5 --draft=false');
      expect(shell.commandsMatching('gh release create')).toHaveLength(isDraft ? 0 : 1);
    },
  );
});

describe('22.2 validating custom artifact declarations', () => {
  test('22.2.1 rejects asset paths outside the staging directory', async ({
    airlock,
    configureTarget,
    containerRelease,
  }) => {
    await configureTarget('ghcr', 'assets = ["../release.json"]');
    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      'relative to the artifact directory',
    );
  });

  test('22.2.2 requires an artifact command for declared assets', async ({ airlock, configureTarget }) => {
    await configureTarget('ghcr', 'assets = ["release.json"]');
    await expect(airlock.run('publish-tagged-target', '--release', 'ci-image-v3.4.5')).rejects.toThrow(
      'declared assets require an artifact_command',
    );
  });

  test('22.2.3 requires release finalization for artifact commands', async ({ airlock, containerRelease }) => {
    await expect(airlock.run('publish-tagged-target', containerRelease.batch.tags[0] ?? '')).rejects.toThrow(
      'artifact commands require --release',
    );
  });

  test('22.2.4 rejects published container releases with missing declared assets during planning', async ({
    containerRelease,
    planReleases,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true });
    shell.on('gh api graphql', '{"data":{"repository":{"release":{"isDraft":false,"releaseAssets":{"nodes":[]}}}}}');
    await expect(planReleases(containerRelease.batch.tags[0])).rejects.toThrow('missing required assets');
    expect(shell).not.toHaveRunMatching('podman');
  });
});
