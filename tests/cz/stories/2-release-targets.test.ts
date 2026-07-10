import { describe, expect, targetsTest as test } from '#fixtures';

const BROKEN_TARGET_MANIFEST = [
  '[[target]]',
  'kind = "npm"',
  'label = "broken-target"',
  'surface = []',
  'tag_prefix = "broken-v"',
  'version = { file = "VERSION", regex = \'^nomatch$\' }',
].join('\n');

describe('2.1 loading release targets from the manifest', () => {
  test('2.1.1 loads every declared target, reading versions from json and regex sources', async ({
    cz,
    logs,
    release,
  }) => {
    release.stageAllPublished();

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    expect(logs).toHaveLogged('Skipping @zyplux/util 1.2.3 (already published)');
    expect(logs).toHaveLogged('Skipping zyplux-cerberus 2.3.4 (already published)');
    expect(logs).toHaveLogged('Skipping ghcr.io/zyplux/ci 3.4.5 (already published)');
  });
});

describe('2.2 reading a version whose regex does not match its source file', () => {
  test('2.2.1 rejects reading a version whose regex does not match the file', async ({ cz, tempDir }) => {
    await tempDir.write('release-targets.toml', BROKEN_TARGET_MANIFEST);
    await tempDir.write('VERSION', '1.2.3\n');

    await expect(cz.run('assert-tag-version', 'broken-v1.2.3')).rejects.toThrow('could not read version from VERSION');
  });
});

describe('2.3 checking whether the ghcr image target is published', () => {
  test('2.3.1 treats a failed registry auth handshake as not published', async ({
    cz,
    logs,
    registries,
    release,
    shell,
  }) => {
    release.stageAllPublished();
    registries.denyGhcrAuth();
    shell.on('gh release list', 'true');

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    expect(logs).toHaveLogged('Skipping ghcr.io/zyplux/ci 3.4.5 (release ci-image-v3.4.5 already exists)');
    expect(logs).not.toHaveLogged('Skipping ghcr.io/zyplux/ci 3.4.5 (already published)');
  });
});

describe("2.4 conforming the repo's own release manifest", () => {
  test('2.4.1 loads a version for every target declared in release-targets.toml', async ({
    cz,
    liveWorkspace,
    logs,
    release,
    repo,
  }) => {
    repo.setRoot(liveWorkspace.root);
    release.stageAllPublished();

    await expect(cz.run('release-bumped-targets')).rejects.toThrow('nothing to release; bump a version first');

    const labels = await liveWorkspace.targetLabels();
    expect(labels).not.toHaveLength(0);
    for (const label of labels) {
      expect(logs.logLines).toContainEqual(expect.stringContaining(`Skipping ${label} `));
    }
  });
});
