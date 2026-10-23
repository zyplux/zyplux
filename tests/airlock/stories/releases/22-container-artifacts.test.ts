import { describe, expect, test } from './releases.ts';

const DIGEST_HEX_LENGTH = 64;
const RETRY_BUILD_COUNT = 2;

describe('22.1 publishing standard container releases', () => {
  test('22.1.1 builds from the declared Dockerfile and context and uploads a digest-pinned manifest', async ({
    airlock,
    configureTarget,
    containerRelease,
    shell,
    tempDir,
  }) => {
    await configureTarget('ghcr', 'dockerfile = "containers/ci/Containerfile"\nbuild_context = "."');
    await airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch));
    expect(containerRelease.readManifest()).toBe(
      `${JSON.stringify({ image: `ghcr.io/zyplux/ci@sha256:${'1'.repeat(DIGEST_HEX_LENGTH)}`, version: '3.4.5' })}\n`,
    );
    const build = shell.calls.find(call => call.program === 'podman' && call.argv[0] === 'build');
    expect(build?.argv).toEqual([
      'build',
      '--file',
      `${tempDir.path}/containers/ci/Containerfile`,
      '--label',
      'org.opencontainers.image.version=3.4.5',
      '--label',
      'org.opencontainers.image.revision=reviewed-sha',
      '-t',
      'ghcr.io/zyplux/ci:3.4.5',
      tempDir.path,
    ]);
    const push = shell.calls.find(call => call.program === 'podman' && call.argv[0] === 'push');
    expect(push?.argv).toEqual(['push', '--digestfile', expect.any(String), 'ghcr.io/zyplux/ci:3.4.5']);
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
    expect(shell.commandsMatching('podman build')).toHaveLength(RETRY_BUILD_COUNT);
    expect(shell.commandsMatching('podman build').at(-1)).toContain('org.opencontainers.image.revision=retry-sha');
  });

  test.for([
    { command: 'podman build', reason: 'command failed', reply: { exitCode: 1, stdout: 'build failed' } },
    { command: 'podman push', reason: 'command failed', reply: { exitCode: 1, stdout: 'push failed' } },
    { command: 'podman push', reason: 'ENOENT', reply: '' },
  ])(
    '22.1.3 keeps releases unpublished and removes credentials when image publication fails (%j)',
    async ({ command, reason, reply }, { airlock, containerRelease, shell }) => {
      shell.on(command, reply);
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
    expect(shell).not.toHaveRunMatching(/podman|gh release (?:create|upload|edit)/);
  });

  test('22.1.5 rejects a finalized release whose image is missing without changing its manifest', async ({
    airlock,
    containerRelease,
    network,
    planReleases,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true });
    network.on(
      `https://ghcr.io/v2/zyplux/ci/manifests/sha256:${'1'.repeat(DIGEST_HEX_LENGTH)}`,
      () => new Response(undefined, { status: 404 }),
    );
    shell.on(
      'gh api graphql',
      '{"data":{"repository":{"release":{"isDraft":false,"releaseAssets":{"nodes":[{"name":"release.json"}]}}}}}',
    );
    await expect(planReleases(containerRelease.batch.tags[0])).rejects.toThrow('is missing image');
    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      `published release ci-image-v3.4.5 is missing image ghcr.io/zyplux/ci@sha256:${'1'.repeat(DIGEST_HEX_LENGTH)}`,
    );
    expect(shell).not.toHaveRunMatching(/podman|gh release (?:create|upload|edit)/);
  });

  test('22.1.6 requires the pushed image in the registry before creating its release', async ({
    airlock,
    containerRelease,
    shell,
  }) => {
    containerRelease.setImagePublished(false);
    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      'container push did not publish image ghcr.io/zyplux/ci:3.4.5',
    );
    expect(shell).not.toHaveRunMatching('gh release');
    expect(shell).toHaveRun('podman logout ghcr.io');
  });

  test('22.1.7 leaves the release as a draft when manifest upload fails', async ({
    airlock,
    containerRelease,
    shell,
  }) => {
    shell.on('gh release upload', { exitCode: 1, stdout: 'upload failed' });
    await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
      'command failed',
    );
    expect(shell).toHaveRunMatching('gh release create ci-image-v3.4.5 --draft');
    expect(shell).not.toHaveRunMatching('gh release edit');
    expect(shell).toHaveRun('podman logout ghcr.io');
  });
});

describe('22.2 validating container releases', () => {
  test.for([
    'build_context = "../outside"',
    'build_context = "/tmp"',
    'dockerfile = "../Dockerfile"',
    'dockerfile = "/tmp/Dockerfile"',
  ])(
    '22.2.1 requires repository-relative build paths (%s)',
    async (fields, { airlock, configureTarget, containerRelease, shell }) => {
      await configureTarget('ghcr', fields);
      await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow(
        'container build paths must be repository-relative',
      );
      expect(shell).not.toHaveRunMatching('podman');
    },
  );

  test.for(['artifact_command = ["custom-builder"]', 'assets = ["custom.json"]'])(
    '22.2.2 rejects unsupported custom builder declarations (%s)',
    async (fields, { configureTarget, planReleases }) => {
      await configureTarget('ghcr', fields);
      await expect(planReleases()).rejects.toThrow('Unrecognized key');
    },
  );

  test('22.2.3 requires release finalization for container publication', async ({ airlock, containerRelease }) => {
    await expect(airlock.run('publish-tagged-target', containerRelease.batch.tags[0] ?? '')).rejects.toThrow(
      'container publication requires --release',
    );
  });

  test('22.2.4 rejects published container releases with missing manifests during planning', async ({
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

  test.for(['', 'sha256:short', `sha512:${'1'.repeat(DIGEST_HEX_LENGTH)}`, `sha256:${'g'.repeat(DIGEST_HEX_LENGTH)}`])(
    '22.2.5 rejects malformed pushed digests before uploading the manifest (%s)',
    async (digest, { airlock, containerRelease, shell }) => {
      containerRelease.setDigest(digest);
      await expect(airlock.run('publish', '--batch', JSON.stringify(containerRelease.batch))).rejects.toThrow();
      expect(shell).not.toHaveRunMatching('gh release');
      expect(shell).toHaveRun('podman logout ghcr.io');
    },
  );
});
