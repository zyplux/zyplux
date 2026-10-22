import { describe, expect, test } from './releases.ts';

describe('18.1 preparing native package releases', () => {
  test('18.1.1 runs Changesets and uv to produce synchronized versions, changelogs and lockfiles', async ({
    cz,
    loadArtifact,
    logs,
    prepareWorkspace,
    tempDir,
  }) => {
    await prepareWorkspace();

    await cz.run('prepare-release');
    await cz.run('list-prepared-releases');

    expect(logs.logLines.at(-1)).toContain('"tag":"util-v1.3.0"');
    expect(logs.logLines.at(-1)).toContain('"tag":"cerberus-v2.3.5"');
    expect(logs.logLines.at(-1)).toContain('Expose reviewed target release notes.');
    expect(await loadArtifact('apps/cerberus/pyproject.toml')).toContain('version = "2.3.5"');
    expect(await loadArtifact('pnpm-lock.yaml')).toContain('apps/cerberus');
    expect(await loadArtifact('uv.lock')).toContain('version = "2.3.5"');
    expect(tempDir.exists('.changeset/feature.md')).toBe(false);

    await expect(cz.run('prepare-release')).rejects.toThrow();
    await cz.run('check-release-notes');
  });

  test('18.1.2 rejects Python version drift before changing any release files', async ({ cz, shell, tempDir }) => {
    await tempDir.write(
      'apps/cerberus/package.json',
      JSON.stringify({ name: 'zyplux-cerberus', private: true, version: '2.4.0' }),
    );

    await expect(cz.run('prepare-release')).rejects.toThrow('package.json and pyproject.toml versions must match');
    expect(shell).not.toHaveRunMatching(/node|pnpm|uv/);
  });
});
