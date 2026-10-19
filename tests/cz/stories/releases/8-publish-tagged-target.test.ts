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
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    shell.on(/pnpm pack/, '');
    shell.on(/^npm publish/, '');

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    await expectNpmPackAndPublish(shell, targets.util.dir);
  });

  test('8.2.6 removes the temporary archive when npm publication fails', async ({
    cz,
    expectNpmPackAndPublish,
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    shell.on(/pnpm pack/, '');
    shell.on(/^npm publish/, { exitCode: 1, stdout: '' });

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
    ]);
  });
});

describe('8.3 publishing a private GitHub npm package', () => {
  test('8.3.1 authenticates the configured registry and lets npm apply publishConfig', async ({
    cz,
    env,
    expectNpmPackAndPublish,
    network,
    shell,
    targets,
    tempDir,
  }) => {
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        name: '@zyplux/util',
        publishConfig: { access: 'restricted', registry: 'https://npm.pkg.github.com' },
        version: '1.2.3',
      }),
    );
    env.set('NODE_AUTH_TOKEN', 'package-read-token');
    network.on('https://npm.pkg.github.com/', () => new Response(undefined, { status: 404 }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    shell.on(/pnpm pack/, '');
    shell.on(/^npm publish/, '');

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    expect(network.requests).toEqual(['https://npm.pkg.github.com/%40zyplux%2Futil/1.2.3']);
    expect(fetchSpy).toHaveBeenCalledWith('https://npm.pkg.github.com/%40zyplux%2Futil/1.2.3', {
      headers: { Authorization: 'Bearer package-read-token' },
      method: 'GET',
    });
    await expectNpmPackAndPublish(shell, targets.util.dir);
  });

  test('8.3.2 rejects missing credentials before checking a private registry', async ({
    cz,
    env,
    network,
    tempDir,
  }) => {
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        publishConfig: { registry: 'https://npm.pkg.github.com' },
        version: '1.2.3',
      }),
    );
    env.set('NODE_AUTH_TOKEN', '');

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow(
      'NODE_AUTH_TOKEN is required to read npm.pkg.github.com',
    );
    expect(network.requests).toEqual([]);
  });

  test('8.3.3 rejects registry failures without attempting publication', async ({ cz, network, shell }) => {
    network.on('https://registry.npmjs.org/', () => new Response(undefined, { status: 403 }));

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow('failed: 403');
    expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
  });

  test('8.3.4 rejects unsupported registry destinations before making a request', async ({ cz, network, tempDir }) => {
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        publishConfig: { registry: 'https://example.com' },
        version: '1.2.3',
      }),
    );

    await expect(cz.run('publish-tagged-target', 'util-v1.2.3')).rejects.toThrow();
    expect(network.requests).toEqual([]);
  });

  test.for(['https://registry.npmjs.org/', 'https://npm.pkg.github.com/'])(
    '8.3.5 accepts supported registry URLs with a trailing slash (%s)',
    async (registry, { cz, env, logs, network, shell, tempDir }) => {
      await tempDir.write(
        'packages/util/package.json',
        JSON.stringify({ publishConfig: { registry }, version: '1.2.3' }),
      );
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on(registry, () => new Response(undefined, { status: 200 }));

      await cz.run('publish-tagged-target', 'util-v1.2.3');

      expect(network.requests).toEqual([`${registry}%40zyplux%2Futil/1.2.3`]);
      expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
      expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
    },
  );

  test.for([
    { '@zyplux:registry': 'https://npm.pkg.github.com/' },
    { '@zyplux:registry': 'https://npm.pkg.github.com/', registry: 'https://registry.npmjs.org' },
  ])(
    '8.3.6 prefers the package scope’s registry setting (%j)',
    async (publishConfig, { cz, env, logs, network, shell, tempDir }) => {
      await tempDir.write('packages/util/package.json', JSON.stringify({ publishConfig, version: '1.2.3' }));
      env.set('NODE_AUTH_TOKEN', 'package-read-token');
      network.on('https://npm.pkg.github.com/', () => new Response(undefined, { status: 200 }));

      await cz.run('publish-tagged-target', 'util-v1.2.3');

      expect(network.requests).toEqual(['https://npm.pkg.github.com/%40zyplux%2Futil/1.2.3']);
      expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; nothing to do');
      expect(shell).not.toHaveRunMatching(/pnpm pack|npm publish/);
    },
  );
});
