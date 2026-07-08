import { describe, expect, notFoundResponse, okResponse, test, workspaceRoot } from '#fixtures';

describe('5.1 validating the target before bootstrapping', () => {
  test('5.1.1 rejects a label no release target owns', async ({ cz }) => {
    await expect(cz.run('bootstrap-npm-target', 'does-not-exist')).rejects.toThrow(
      "no release target labeled 'does-not-exist' in release-targets.toml",
    );
  });

  test('5.1.2 rejects a target that is not an npm target', async ({ cz }) => {
    await expect(cz.run('bootstrap-npm-target', 'zyplux-cerberus')).rejects.toThrow(
      "bootstrap is npm-only; 'zyplux-cerberus' is a pypi target",
    );
  });
});

describe('5.2 bootstrapping an npm target', () => {
  test("5.2.1 skips publishing when the target's version is already on npm", async ({
    cz,
    findTarget,
    logs,
    network,
    repo,
    shell,
  }) => {
    repo.setRoot(workspaceRoot);
    network.otherwise(() => okResponse());
    const util = await findTarget('@zyplux/util');

    await cz.run('bootstrap-npm-target', '@zyplux/util');

    expect(logs.logLines).toContain(
      `@zyplux/util ${util.version} is already on npm — enable its trusted publisher; no bootstrap needed`,
    );
    expect(shell.commandsMatching(/bun pm pack/)).toHaveLength(0);
  });

  test('5.2.2 publishes the target when its version is not yet on npm', async ({
    cz,
    findTarget,
    logs,
    network,
    repo,
    shell,
  }) => {
    repo.setRoot(workspaceRoot);
    network.otherwise(() => notFoundResponse());
    shell.on(/bun pm pack/, '');
    const util = await findTarget('@zyplux/util');

    await cz.run('bootstrap-npm-target', '@zyplux/util');

    expect(shell.commands).toContain(
      `cd ${util.dir} && bun pm pack && bunx npm@latest publish ./*.tgz --access public`,
    );
    expect(logs.logLines).toContain(
      `Published @zyplux/util ${util.version}. Enable its trusted publisher on npmjs.com; later releases publish via OIDC.`,
    );
  });
});
