import { describe, expect, targetsTest as test } from '#fixtures';

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
    logs,
    registries,
    shell,
  }) => {
    registries.setPublished({ npmPublished: true });

    await cz.run('bootstrap-npm-target', '@zyplux/util');

    expect(logs).toHaveLogged(
      '@zyplux/util 1.2.3 is already on npm — enable its trusted publisher; no bootstrap needed',
    );
    expect(shell).not.toHaveRunMatching(/bun pm pack/);
  });

  test('5.2.2 publishes the target when its version is not yet on npm', async ({
    cz,
    logs,
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    shell.on(/bun pm pack/, '');

    await cz.run('bootstrap-npm-target', '@zyplux/util');

    expect(shell).toHaveRun(`cd ${targets.util.dir} && bun pm pack && bunx npm@11 publish ./*.tgz --access public`);
    expect(logs).toHaveLogged(
      'Published @zyplux/util 1.2.3. Enable its trusted publisher on npmjs.com; later releases publish via OIDC.',
    );
  });
});
