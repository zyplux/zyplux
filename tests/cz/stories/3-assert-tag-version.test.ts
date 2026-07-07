import { describe, expect, test } from '#fixtures';

describe('3.1 asserting a tag against the release manifest', () => {
  test("3.1.1 logs a confirmation when the tag matches its target's declared version", async ({ cz, findTarget, logs }) => {
    const util = await findTarget('@zyplux/util');

    await cz.run('assert-tag-version', `util-v${util.version}`);

    expect(logs.logLines).toContain(`@zyplux/util ${util.version} matches util-v${util.version}`);
  });

  test('3.1.2 rejects a tag no release target owns', async ({ cz }) => {
    await expect(cz.run('assert-tag-version', 'mystery-v1.0.0')).rejects.toThrow("no release target in release-targets.toml owns tag 'mystery-v1.0.0'");
  });

  test('3.1.3 rejects a tag whose version does not match the manifest', async ({ cz }) => {
    await expect(cz.run('assert-tag-version', 'cerberus-v0.0.0-does-not-exist')).rejects.toThrow('does not match zyplux-cerberus version');
  });
});
