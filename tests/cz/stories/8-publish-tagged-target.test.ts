import { describe, expect, targetsTest as test } from '#fixtures';

const MISSING_GHCR_CREDENTIALS: [missingName: string, ghToken: string, githubActor: string][] = [
  ['GH_TOKEN', '', 'zyplux-bot'],
  ['GITHUB_ACTOR', 'gh-token', ''],
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
    expect(shell).not.toHaveRunMatching(/bun pm pack|podman|uv build/);
  });
});

describe('8.2 publishing to each registry kind', () => {
  test('8.2.1 packs and publishes an npm target', async ({ cz, registries, shell, targets }) => {
    registries.setPublished({ npmPublished: false });
    shell.on(/bun pm pack/, '');

    await cz.run('publish-tagged-target', 'util-v1.2.3');

    expect(shell.commandsMatching(/bun pm pack/)).toEqual([
      `cd ${targets.util.dir} && bun pm pack && bunx npm@11 publish ./*.tgz --access public`,
    ]);
  });

  test('8.2.2 builds and publishes a pypi target', async ({ cz, registries, shell }) => {
    registries.setPublished({ pypiPublished: false });
    shell.on('uv build', '');

    await cz.run('publish-tagged-target', 'cerberus-v2.3.4');

    expect(shell.commandsMatching('uv build')).toEqual(['uv build --package zyplux-cerberus && uv publish']);
  });

  test.for(MISSING_GHCR_CREDENTIALS)(
    '8.2.3 requires GH_TOKEN and GITHUB_ACTOR before pushing a ghcr target',
    async ([missingName, ghToken, githubActor], { cz, env, registries, shell }) => {
      registries.setPublished({ ghcrPublished: false });
      env.set('GH_TOKEN', ghToken);
      env.set('GITHUB_ACTOR', githubActor);

      await expect(cz.run('publish-tagged-target', 'ci-image-v3.4.5')).rejects.toThrow(
        `${missingName} is required to push to GHCR`,
      );
      expect(shell).not.toHaveRunMatching('podman');
    },
  );

  test('8.2.4 tags and pushes a versioned and latest ghcr image', async ({ cz, env, registries, shell, targets }) => {
    registries.setPublished({ ghcrPublished: false });
    env.set('GH_TOKEN', 'gh-token');
    env.set('GITHUB_ACTOR', 'zyplux-bot');
    shell.on('podman', '');

    await cz.run('publish-tagged-target', 'ci-image-v3.4.5');

    expect(shell.commandsMatching('podman')).toEqual([
      expect.stringContaining('podman login ghcr.io -u zyplux-bot --password-stdin < '),
      `podman build -t ghcr.io/zyplux/ci:3.4.5 -t ghcr.io/zyplux/ci:latest ${targets.ci.dir}`,
      'podman push ghcr.io/zyplux/ci:3.4.5',
      'podman push ghcr.io/zyplux/ci:latest',
    ]);
  });
});
