import { vi } from 'vitest';

import { describe, expect, test } from './releases.ts';

const MISSING_GHCR_CREDENTIALS: [shape: string, missingName: string, ghToken: string, githubActor: string][] = [
  ['3 requires GH_TOKEN before pushing a ghcr target', 'GH_TOKEN', '', 'zyplux-bot'],
  ['4 requires GITHUB_ACTOR before pushing a ghcr target', 'GITHUB_ACTOR', 'gh-token', ''],
];

describe('8.1 skipping an already-published target', () => {
  test("8.1.1 logs and does nothing when the tag's version is already published", async ({
    cz,
    logs,
    registries,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
    expect(shell).not.toHaveRunMatching(/pnpm pack|podman|uv build/);
  });
});

describe('8.2 publishing to each registry kind', () => {
  test('8.2.1 packs and publishes an npm target', async ({
    cz,
    expectNpmPackAndPublish,
    npmTarget,
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    npmTarget.stagePublish();

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    await expectNpmPackAndPublish(shell, targets.util.dir);
  });

  test('8.2.6 removes the temporary archive when npm publication fails', async ({
    cz,
    expectNpmPackAndPublish,
    npmTarget,
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    npmTarget.stagePublish(1);

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow('command failed with exit code 1');

    await expectNpmPackAndPublish(shell, targets.util.dir);
  });

  test('8.2.2 builds and publishes a pypi target', async ({ cz, registries, shell }) => {
    registries.setPublished({ pypiPublished: false });
    shell.on('uv build', '');
    shell.on('uv publish', '');

    await cz.run('publish-tagged-target', 'cerberus-v2.3.4');

    expect(shell.commandsMatching('uv build')).toEqual(['uv build --package zyplux-cerberus']);
    expect(shell.commandsMatching('uv publish')).toEqual(['uv publish']);
  });

  test.for(MISSING_GHCR_CREDENTIALS)(
    '8.2.%s',
    async ([, missingName, ghToken, githubActor], { cz, env, registries, shell }) => {
      registries.setPublished({ ghcrPublished: false });
      env.set('GH_TOKEN', ghToken);
      env.set('GITHUB_ACTOR', githubActor);

      await expect(cz.run('publish-tagged-target', 'ci-image-v3.4.5')).rejects.toThrow(
        `${missingName} is required to push to GHCR`,
      );
      expect(shell).not.toHaveRunMatching('podman');
    },
  );

  test('8.2.5 tags and pushes a versioned and latest ghcr image', async ({ cz, env, registries, shell, targets }) => {
    registries.setPublished({ ghcrPublished: false });
    env.set('GH_TOKEN', 'gh-token');
    env.set('GITHUB_ACTOR', 'zyplux-bot');
    shell.on('podman', '');

    await cz.run('publish-tagged-target', 'ci-image-v3.4.5');

    expect(shell.calls).toContainEqual({
      argv: ['login', 'ghcr.io', '-u', 'zyplux-bot', '--password-stdin'],
      program: 'podman',
      stdin: 'gh-token',
    });
    expect(shell.commandsMatching('podman')).toEqual([
      'podman login ghcr.io -u zyplux-bot --password-stdin',
      `podman build -t ghcr.io/zyplux/ci:3.4.5 -t ghcr.io/zyplux/ci:latest ${targets.ci.dir}`,
      'podman push ghcr.io/zyplux/ci:3.4.5',
      'podman push ghcr.io/zyplux/ci:latest',
      'podman logout ghcr.io',
    ]);
  });

  test.for([
    { command: 'podman login', shouldLogout: false },
    { command: 'podman build', shouldLogout: true },
    { command: 'podman push', shouldLogout: true },
  ])(
    '8.2.7 removes GHCR credentials after a successful login when publication fails (%j)',
    async ({ command, shouldLogout }, { cz, env, registries, shell }) => {
      registries.setPublished({ ghcrPublished: false });
      env.set('GH_TOKEN', 'gh-token');
      env.set('GITHUB_ACTOR', 'zyplux-bot');
      shell.on('podman', '');
      shell.on(command, { exitCode: 1, stdout: '' });

      await expect(cz.run('publish-tagged-target', 'ci-image-v3.4.5')).rejects.toThrow(
        'command failed with exit code 1',
      );

      expect(shell.commandsMatching('podman logout')).toEqual(shouldLogout ? ['podman logout ghcr.io'] : []);
    },
  );
});

describe('8.3 publishing a private GitHub npm package', () => {
  test('8.3.1 authenticates the configured registry and lets npm apply publishConfig', async ({
    cz,
    env,
    expectNpmPackAndPublish,
    network,
    npmTarget,
    shell,
    targets,
  }) => {
    await npmTarget.setPublishConfig({ access: 'restricted', registry: 'https://npm.pkg.github.com' });
    env.set('NODE_AUTH_TOKEN', 'package-read-token');
    network.on('https://npm.pkg.github.com/', () => new Response(undefined, { status: 404 }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    npmTarget.stagePublish();

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    expect(network.requests).toEqual(['https://npm.pkg.github.com/%40zyplux%2Futil']);
    expect(fetchSpy).toHaveBeenCalledWith('https://npm.pkg.github.com/%40zyplux%2Futil', {
      headers: { Authorization: 'Bearer package-read-token' },
      method: 'GET',
    });
    await expectNpmPackAndPublish(shell, targets.util.dir);
  });

  test('8.3.2 rejects missing credentials before checking a private registry', async ({
    cz,
    env,
    network,
    npmTarget,
  }) => {
    await npmTarget.setPublishConfig({ registry: 'https://npm.pkg.github.com' });
    env.set('NODE_AUTH_TOKEN', '');

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow(
      'NODE_AUTH_TOKEN is required to read npm.pkg.github.com',
    );
    expect(network.requests).toEqual([]);
  });

  test.for([
    { registry: 'https://registry.npmjs.org', status: 403 },
    { registry: 'https://registry.npmjs.org', status: 502 },
    { registry: 'https://npm.pkg.github.com', status: 403 },
    { registry: 'https://npm.pkg.github.com', status: 502 },
  ])(
    '8.3.3 rejects registry failures without attempting publication (%j)',
    async ({ registry, status }, { cz, env, network, npmTarget, shell }) => {
      await npmTarget.setPublishConfig({ registry });
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on(registry, () => new Response(undefined, { status }));

      await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow(`failed: ${status}`);
      expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
    },
  );

  test('8.3.4 rejects unsupported registry destinations before making a request', async ({
    cz,
    network,
    npmTarget,
  }) => {
    await npmTarget.setPublishConfig({ registry: 'https://example.com' });

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow();
    expect(network.requests).toEqual([]);
  });

  test.for([
    { packageUrl: 'https://registry.npmjs.org/%40zyplux%2Futil', registry: 'https://registry.npmjs.org/' },
    { packageUrl: 'https://npm.pkg.github.com/%40zyplux%2Futil', registry: 'https://npm.pkg.github.com/' },
  ])(
    '8.3.5 accepts supported registry URLs with a trailing slash (%j)',
    async ({ packageUrl, registry }, { cz, env, logs, network, npmTarget, shell }) => {
      await npmTarget.setPublishConfig({ registry });
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on(registry, () => Response.json({ versions: { '1.2.3': {} } }));

      await cz.run('publish-tagged-target', 'util-v1.2.3');

      expect(network.requests).toEqual([packageUrl]);
      expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
      expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
    },
  );

  test.for([
    { '@zyplux:registry': 'https://npm.pkg.github.com/' },
    { '@zyplux:registry': 'https://npm.pkg.github.com/', registry: 'https://registry.npmjs.org' },
  ])(
    '8.3.6 prefers the package scope’s registry setting (%j)',
    async (publishConfig, { cz, env, logs, network, npmTarget, shell }) => {
      await npmTarget.setPublishConfig(publishConfig);
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on('https://npm.pkg.github.com/', () => Response.json({ versions: { '1.2.3': {} } }));

      await cz.run('publish-tagged-target', 'util-v1.2.3');

      expect(network.requests).toEqual(['https://npm.pkg.github.com/%40zyplux%2Futil']);
      expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
      expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
    },
  );

  test.for([
    { isPublished: false, registry: 'https://registry.npmjs.org', versions: { '1.2.2': {} } },
    { isPublished: true, registry: 'https://registry.npmjs.org', versions: { '1.2.2': {}, '1.2.3': {} } },
    { isPublished: false, registry: 'https://npm.pkg.github.com', versions: { '1.2.2': {} } },
    { isPublished: true, registry: 'https://npm.pkg.github.com', versions: { '1.2.2': {}, '1.2.3': {} } },
  ])(
    '8.3.7 checks the requested version in registry package metadata (%j)',
    async (
      { isPublished, registry, versions },
      { cz, env, expectNpmPackAndPublish, logs, network, npmTarget, shell, targets },
    ) => {
      await npmTarget.setPublishConfig({ registry });
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on(registry, () => new Response(undefined, { status: 502 }));
      network.on(/^https:\/\/(?:registry\.npmjs\.org|npm\.pkg\.github\.com)\/%40zyplux%2Futil$/u, () =>
        Response.json({ versions }),
      );
      npmTarget.stagePublish();

      await cz.run('publish-tagged-target', 'util-v1.2.3');

      expect(network.requests).toEqual([`${registry}/%40zyplux%2Futil`]);

      if (isPublished) {
        expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
        expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
      } else {
        await expectNpmPackAndPublish(shell, targets.util.dir);
      }
    },
  );

  test('8.3.8 rejects malformed package metadata without attempting publication', async ({
    cz,
    env,
    network,
    npmTarget,
    shell,
  }) => {
    await npmTarget.setPublishConfig({ registry: 'https://npm.pkg.github.com' });
    env.set('NODE_AUTH_TOKEN', 'package-read-token');
    network.on('https://npm.pkg.github.com/', () => Response.json({}));

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow();
    expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
  });
});

describe('8.4 completing GitHub release metadata after publication', () => {
  test.for([
    { isArtifactPublished: false, isReleaseCreated: false },
    { isArtifactPublished: true, isReleaseCreated: false },
    { isArtifactPublished: false, isReleaseCreated: true },
    { isArtifactPublished: true, isReleaseCreated: true },
  ])(
    '8.4.1 publishes only missing artifacts and creates only missing GitHub releases at HEAD (%j)',
    async (
      { isArtifactPublished, isReleaseCreated },
      { cz, expectGithubRelease, expectNpmPackAndPublish, npmTarget, registries, repo, shell, targets },
    ) => {
      registries.setPublished({ npmPublished: isArtifactPublished });
      repo.setHeadSha('reviewed-sha');
      shell.on(
        'gh api graphql',
        isReleaseCreated
          ? '{"data":{"repository":{"release":{"id":"release-id"}}}}'
          : '{"data":{"repository":{"release":null}}}',
      );
      npmTarget.stagePublish();

      await cz.run('publish-tagged-target', '--release', 'util-v1.2.3');

      if (isArtifactPublished) expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
      else await expectNpmPackAndPublish(shell, targets.util.dir);
      if (isReleaseCreated) expect(shell).not.toHaveRunMatching('gh release create');
      else {
        await expectGithubRelease(shell, 'util-v1.2.3', 'reviewed-sha');
      }
    },
  );

  test('8.4.2 leaves GitHub release metadata unpublished when the registry rejects publication', async ({
    cz,
    npmTarget,
    registries,
    shell,
  }) => {
    registries.setPublished({ npmPublished: false });
    npmTarget.stagePublish(1);

    await expect(cz.run('publish-tagged-target', '--release', 'util-v1.2.3')).rejects.toThrow(
      'command failed with exit code 1',
    );

    expect(shell).not.toHaveRunMatching(/gh api graphql|gh release create/);
  });

  test('8.4.3 repairs GHCR release metadata without logging in or out when the image exists', async ({
    cz,
    expectGithubRelease,
    registries,
    repo,
    shell,
  }) => {
    registries.setPublished({ ghcrPublished: true });
    repo.setHeadSha('reviewed-sha');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await cz.run('publish-tagged-target', '--release', 'ci-image-v3.4.5');

    expect(shell).not.toHaveRunMatching('podman');
    await expectGithubRelease(shell, 'ci-image-v3.4.5', 'reviewed-sha');
  });
});
