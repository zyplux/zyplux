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

    expectNpmPackAndPublish(shell, targets.util.dir, 'zyplux-util-1.2.3.tgz');
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
