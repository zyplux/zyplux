import { describe, expect, notFoundResponse, test, vi, workspaceRoot } from '#fixtures';

const MISSING_GHCR_CREDENTIALS: [missingName: string, ghToken: string, githubActor: string][] = [
  ['GH_TOKEN', '', 'zyplux-bot'],
  ['GITHUB_ACTOR', 'gh-token', ''],
];

describe('8.1 skipping an already-published target', () => {
  test("8.1.1 logs and does nothing when the tag's version is already published", async ({ cz, findTarget, logs, registries, repo, shell }) => {
    repo.setRoot(workspaceRoot);
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
    const util = await findTarget('@zyplux/util');

    await cz.run('publish-tagged-target', `util-v${util.version}`);

    expect(logs.logLines).toContain(`@zyplux/util ${util.version} is already published; nothing to do`);
    expect(shell.commandsMatching(/bun pm pack|podman|uv build/)).toHaveLength(0);
  });
});

describe('8.2 publishing to each registry kind', () => {
  test('8.2.1 packs and publishes an npm target', async ({ cz, findTarget, network, repo, shell }) => {
    repo.setRoot(workspaceRoot);
    network.otherwise(() => notFoundResponse());
    shell.on(/bun pm pack/, '');
    const util = await findTarget('@zyplux/util');

    await cz.run('publish-tagged-target', `util-v${util.version}`);

    expect(shell.commandsMatching(/bun pm pack/)).toEqual([`cd ${util.dir} && bun pm pack && bunx npm@latest publish ./*.tgz --access public`]);
  });

  test('8.2.2 builds and publishes a pypi target', async ({ cz, findTarget, network, repo, shell }) => {
    repo.setRoot(workspaceRoot);
    network.otherwise(() => notFoundResponse());
    shell.on('uv build', '');
    const cerberus = await findTarget('zyplux-cerberus');

    await cz.run('publish-tagged-target', `cerberus-v${cerberus.version}`);

    expect(shell.commandsMatching('uv build')).toEqual(['uv build --package zyplux-cerberus && uv publish']);
  });

  test.for(MISSING_GHCR_CREDENTIALS)(
    '8.2.3 requires GH_TOKEN and GITHUB_ACTOR before pushing a ghcr target',
    async ([missingName, ghToken, githubActor], { cz, findTarget, registries, repo, shell }) => {
      repo.setRoot(workspaceRoot);
      registries.setPublished({ ghcrPublished: false, npmPublished: false, pypiPublished: false });
      vi.stubEnv('GH_TOKEN', ghToken);
      vi.stubEnv('GITHUB_ACTOR', githubActor);
      const ci = await findTarget('ghcr.io/zyplux/ci');

      await expect(cz.run('publish-tagged-target', `ci-image-v${ci.version}`)).rejects.toThrow(`${missingName} is required to push to GHCR`);
      expect(shell.commandsMatching('podman')).toHaveLength(0);
    },
  );

  test('8.2.4 tags and pushes a versioned and latest ghcr image', async ({ cz, findTarget, registries, repo, shell }) => {
    repo.setRoot(workspaceRoot);
    registries.setPublished({ ghcrPublished: false, npmPublished: false, pypiPublished: false });
    vi.stubEnv('GH_TOKEN', 'gh-token');
    vi.stubEnv('GITHUB_ACTOR', 'zyplux-bot');
    shell.on('podman', '');
    const ci = await findTarget('ghcr.io/zyplux/ci');

    await cz.run('publish-tagged-target', `ci-image-v${ci.version}`);

    expect(shell.commandsMatching('podman')).toEqual([
      expect.stringContaining('podman login ghcr.io -u zyplux-bot --password-stdin < '),
      `podman build -t ghcr.io/zyplux/ci:${ci.version} -t ghcr.io/zyplux/ci:latest ${ci.dir}`,
      `podman push ghcr.io/zyplux/ci:${ci.version}`,
      'podman push ghcr.io/zyplux/ci:latest',
    ]);
  });
});
