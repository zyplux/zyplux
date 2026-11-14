import { describe, expect, test } from './workspace.ts';

const DOCKER_MANIFEST_URL = 'https://registry-1.docker.io/v2/library/node/manifests/';

describe('15.1 upgrading a mixed workspace', () => {
  test('15.1.1 uses the newest same-major Node release with a real Docker registry manifest', async ({
    cz,
    network,
    shell,
    upgradeWorkspace,
  }) => {
    await upgradeWorkspace.stage({ python: true });
    upgradeWorkspace.stubReleases();
    shell.otherwise('');
    shell.on('git ls-files', 'apps/demo/Dockerfile\0');

    await cz.run('upgrade');

    expect(network.requests).not.toContain(`${DOCKER_MANIFEST_URL}27.1.0-slim`);
    expect(network.requests).toContain(`${DOCKER_MANIFEST_URL}26.8.0-slim`);
    expect(network.requests).toContain(`${DOCKER_MANIFEST_URL}26.7.1-slim`);
    expect(shell.commands).toEqual([
      'pnpm self-update 12',
      'pnpm runtime set node 26.7.1',
      'git ls-files -z -- *Dockerfile*',
      'pnpm pkg set toolchain.turbo=2.11',
      'pnpm update --recursive --include-workspace-root --latest',
      'uv lock --upgrade',
      'uvx uv-bump -v',
      'uv sync --all-packages --all-groups',
    ]);
    await expect(upgradeWorkspace.readDockerfile()).resolves.toMatch(/^ARG NODE_VERSION=26\.7\.1/mu);
  });

  test('15.1.2 uses pnpm selection in interactive mode and leaves declined toolchain pins alone', async ({
    cz,
    prompt,
    shell,
    upgradeWorkspace,
  }) => {
    await upgradeWorkspace.stage();
    upgradeWorkspace.stubReleases();
    shell.otherwise('');

    await cz.run('upgrade', '--interactive');

    expect(prompt.messages).toEqual([
      'upgrade Node from 26.7.0 to 26.7.1? [y/N] ',
      'upgrade turbo from 2.10 to 2.11? [y/N] ',
    ]);
    expect(shell.commands).toEqual([
      'pnpm self-update 12',
      'pnpm update --recursive --include-workspace-root --latest --interactive',
    ]);
    await expect(upgradeWorkspace.readDockerfile()).resolves.toMatch(/^ARG NODE_VERSION=26\.7\.0/mu);
  });

  test('15.1.3 supports a JavaScript-only workspace without an external tool pin', async ({
    cz,
    network,
    shell,
    upgradeWorkspace,
  }) => {
    await upgradeWorkspace.stage({ nodeVersion: '26.7.1', turbo: false });
    upgradeWorkspace.stubReleases();
    shell.otherwise('');

    await cz.run('upgrade');

    expect(network.requests).not.toContain('https://registry.npmjs.org/turbo/latest');
    expect(shell.commands).toEqual([
      'pnpm self-update 12',
      'pnpm update --recursive --include-workspace-root --latest',
    ]);
  });
});
