import { describe, expect, notFoundResponse, okResponse, test } from '#fixtures';

const BROKEN_TARGET_MANIFEST = [
  '[[target]]',
  'kind = "npm"',
  'label = "broken-target"',
  'surface = []',
  'tag_prefix = "broken-v"',
  'version = { file = "VERSION", regex = \'^nomatch$\' }',
].join('\n');

describe('2.1 loading release targets from the manifest', () => {
  test('2.1.1 loads every target declared in the manifest', async ({ cz, logs, registries, repo }) => {
    repo.syncMain('sha-head');
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    for (const label of [
      '@zyplux/cz',
      '@zyplux/eslint-config',
      '@zyplux/tests-fixtures',
      '@zyplux/tsconfig',
      '@zyplux/util',
      'zyplux-cerberus',
      'zyplux-util',
      'ghcr.io/zyplux/ci',
    ]) {
      expect(logs.logLines).toContainEqual(expect.stringContaining(`Skipping ${label} `));
    }
  });

  test('2.1.2 reads each target version from its json and regex sources', async ({
    cz,
    findTarget,
    logs,
    registries,
    repo,
  }) => {
    repo.syncMain('sha-head');
    registries.setPublished({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
    const util = await findTarget('@zyplux/util');
    const cerberus = await findTarget('zyplux-cerberus');

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    expect(logs.logLines).toContain(`Skipping @zyplux/util ${util.version} (already published)`);
    expect(logs.logLines).toContain(`Skipping zyplux-cerberus ${cerberus.version} (already published)`);
  });
});

describe('2.2 reading a version whose regex does not match its source file', () => {
  test('2.2.1 rejects reading a version whose regex does not match the file', async ({ cz, repo, tempDir }) => {
    await tempDir.write('release-targets.toml', BROKEN_TARGET_MANIFEST);
    await tempDir.write('VERSION', '1.2.3\n');
    repo.setRoot(tempDir.path);

    await expect(cz.run('assert-tag-version', 'broken-v1.2.3')).rejects.toThrow('could not read version from VERSION');
  });
});

describe('2.3 checking whether the ghcr image target is published', () => {
  test('2.3.1 treats a failed registry auth handshake as not published', async ({
    cz,
    findTarget,
    logs,
    network,
    repo,
    shell,
  }) => {
    repo.syncMain('sha-head');
    network.on('https://ghcr.io/token', () => notFoundResponse());
    network.otherwise(() => okResponse());
    shell.on('gh release list', 'true');
    const ci = await findTarget('ghcr.io/zyplux/ci');

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    expect(logs.logLines).toContain(
      `Skipping ghcr.io/zyplux/ci ${ci.version} (release ci-image-v${ci.version} already exists)`,
    );
    expect(logs.logLines).not.toContain(`Skipping ghcr.io/zyplux/ci ${ci.version} (already published)`);
  });
});
