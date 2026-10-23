// unparametrized
import { describe, expect, test } from './releases.ts';

describe('5.1 validating the target before bootstrapping', () => {
  test('5.1.1 rejects a label no release target owns', async ({ airlock }) => {
    await expect(airlock.run('bootstrap-npm-target', 'does-not-exist')).rejects.toThrow(
      "no release target labeled 'does-not-exist' in airlock-targets.toml",
    );
  });

  test('5.1.2 rejects a target that is not an npm target', async ({ airlock }) => {
    await expect(airlock.run('bootstrap-npm-target', 'zyplux-cerberus')).rejects.toThrow(
      "bootstrap is npm-only; 'zyplux-cerberus' is a pypi target",
    );
  });
});

describe('5.2 bootstrapping an npm target', () => {
  test("5.2.1 skips publishing when the target's version is already on npm", async ({
    airlock,
    logs,
    registries,
    shell,
  }) => {
    registries.setPublished({ npmPublished: true });

    await airlock.run('bootstrap-npm-target', '@zyplux/util');

    expect(logs).toHaveLogged('@zyplux/util 1.2.3 is already published; no bootstrap needed');
    expect(shell).not.toHaveRunMatching(/pnpm pack/);
  });

  test('5.2.2 publishes the target with the terminal connected for npm authentication', async ({
    airlock,
    expectNpmPublish,
    logs,
    registries,
    shell,
    targets,
  }) => {
    registries.setPublished({ npmPublished: false });
    shell.on(/pnpm pack/, '');
    shell.on(/^pnpm publish/, '');

    await airlock.run('bootstrap-npm-target', '@zyplux/util');

    expectNpmPublish(shell, targets.util.dir);
    expect(logs).toHaveLogged(
      'Published @zyplux/util 1.2.3. Configure registry authentication in the release workflow.',
    );
  });
});
