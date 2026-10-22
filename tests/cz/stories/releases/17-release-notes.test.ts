import { describe, expect, test } from './releases.ts';

describe('17.1 listing prepared releases', () => {
  test('17.1.1 emits version-specific notes and target metadata without registry access', async ({
    cz,
    logs,
    network,
  }) => {
    await cz.run('list-prepared-releases');

    expect(logs.logLines).toEqual([
      JSON.stringify([
        {
          kind: 'npm',
          label: '@zyplux/util',
          notes: '### Patch Changes\n\n- Publish the reviewed utility changes.',
          tag: 'util-v1.2.3',
          version: '1.2.3',
        },
        {
          kind: 'pypi',
          label: 'zyplux-cerberus',
          notes: '### Patch Changes\n\n- Validate repository release contracts.',
          tag: 'cerberus-v2.3.4',
          version: '2.3.4',
        },
        {
          kind: 'ghcr',
          label: 'ghcr.io/zyplux/ci',
          notes: '### Patch Changes\n\n- Refresh the CI container.',
          tag: 'ci-image-v3.4.5',
          version: '3.4.5',
        },
      ]),
    ]);
    expect(network.requests).toEqual([]);
  });

  test('17.1.2 preserves Markdown examples and excludes neighboring release versions', async ({
    cz,
    logs,
    tempDir,
  }) => {
    await tempDir.write(
      'packages/util/CHANGELOG.md',
      '# Utility\n\n## 1.2.3\n\n- Preserve examples.\n\n```md\n## 9.9.9\n- Example heading.\n```\n\n## 1.2.2\n\n- Earlier release.\n',
    );

    await cz.run('list-prepared-releases');

    expect(logs.logLines[0]).toContain('Preserve examples.');
    expect(logs.logLines[0]).toContain('Example heading.');
    expect(logs.logLines[0]).not.toContain('Earlier release.');
  });
});

describe('17.2 validating release preparation', () => {
  test('17.2.1 validates prepared releases without writes or network requests', async ({
    cz,
    logs,
    network,
    shell,
  }) => {
    await cz.run('check-release-notes');

    expect(logs.logLines).toEqual([]);
    expect(network.requests).toEqual([]);
    expect(shell).not.toHaveRunMatching(/gh|pnpm|uv/);
  });

  test('17.2.2 rejects unconsumed fragments', async ({ cz, tempDir }) => {
    await tempDir.write('.changeset/unfinished.md', '---\n"@zyplux/util": patch\n---\n\nFix a utility.\n');

    await expect(cz.run('check-release-notes')).rejects.toThrow('Unconsumed changesets: unfinished');
  });

  test.for<[string, string]>([
    ['missing version', '## 1.2.2\n\n- Earlier notes.\n'],
    ['empty section', '## 1.2.3\n\n### Patch Changes\n'],
    ['empty bullet', '## 1.2.3\n\n-\n'],
    ['example only', '## 1.2.3\n\n```md\n- Example text.\n```\n'],
  ])('17.2.3 rejects a changelog with %s', async ([, markdown], { cz, tempDir }) => {
    await tempDir.write('packages/util/CHANGELOG.md', markdown);

    await expect(cz.run('check-release-notes')).rejects.toThrow(/no release notes|no changelog entries/);
  });

  test.for([
    { name: 'zyplux-cerberus', private: true, version: '2.3.5' },
    { name: 'another-package', private: true, version: '2.3.4' },
    { name: 'zyplux-cerberus', private: false, version: '2.3.4' },
  ])('17.2.4 rejects inconsistent Python tracking manifests (%j)', async (manifest, { cz, tempDir }) => {
    await tempDir.write('apps/cerberus/package.json', JSON.stringify(manifest));

    await expect(cz.run('check-release-notes')).rejects.toThrow();
  });
});

const publicationCases = [
  {
    args: ['publish-tagged-target', '--release', 'util-v1.2.3'],
    directory: 'packages/util',
    notes: '### Patch Changes\n\n- Publish the reviewed utility changes.\n',
    tag: 'util-v1.2.3',
  },
  {
    args: ['release-bumped-targets'],
    directory: 'apps/cerberus',
    notes: '### Patch Changes\n\n- Validate repository release contracts.\n',
    tag: 'cerberus-v2.3.4',
  },
];

describe('17.3 publishing reviewed notes', () => {
  test.for(publicationCases)(
    '17.3.1 sends the exact target entry to GitHub (%j)',
    async ({ args, notes, tag }, { cz, expectGithubRelease, release, releaseNotes, shell }) => {
      release.stagePendingCerberus();
      release.queueRun('999', { conclusion: 'success', status: 'completed' });
      releaseNotes.capture();

      await cz.run(...args);

      expect(releaseNotes.read()).toBe(notes);
      await expectGithubRelease(shell, tag, 'sha-head');
    },
  );

  test.for(publicationCases)(
    '17.3.2 rejects missing notes before publication (%j)',
    async ({ args, directory }, { cz, release, shell, tempDir }) => {
      release.stagePendingCerberus();
      await tempDir.write(`${directory}/CHANGELOG.md`, '# Releases\n');

      await expect(cz.run(...args)).rejects.toThrow('no release notes');
      expect(shell).not.toHaveRunMatching(/gh release create|npm publish|uv publish|podman build/);
    },
  );
});
