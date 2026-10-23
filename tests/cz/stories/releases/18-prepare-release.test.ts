import { describe, expect, test } from './releases.ts';

describe('18.1 preparing native package releases', () => {
  test('18.1.1 runs pnpm versioning and uv to produce synchronized versions, changelogs and lockfiles', async ({
    cz,
    loadArtifact,
    logs,
    prepareWorkspace,
    shell,
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
    expect(shell).toHaveRun('pnpm version -r --no-git-checks --config.@zyplux:registry=https://registry.npmjs.org');

    const changelog = await loadArtifact('packages/util/CHANGELOG.md');
    await cz.run('prepare-release');
    expect(await loadArtifact('packages/util/CHANGELOG.md')).toBe(changelog);
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

  test('18.1.3 stops before Python synchronization when native versioning fails', async ({
    cz,
    loadArtifact,
    prepareWorkspace,
    shell,
  }) => {
    await prepareWorkspace();
    shell.on('pnpm version', { exitCode: 1, stdout: 'Registry lookup failed.' });

    await expect(cz.run('prepare-release')).rejects.toThrow('command failed');

    expect(await loadArtifact('apps/cerberus/pyproject.toml')).toContain('version = "2.3.4"');
    expect(shell).not.toHaveRunMatching(/pnpm install|uv/);
  });

  test('18.1.4 propagates a workspace dependency bump through pnpm', async ({
    cz,
    loadArtifact,
    loadPackageVersion,
    prepareWorkspace,
    tempDir,
  }) => {
    await prepareWorkspace();
    await tempDir.write(
      'packages/consumer/package.json',
      JSON.stringify({
        dependencies: { '@zyplux/util': 'workspace:*' },
        name: 'release-consumer',
        private: true,
        version: '5.0.0',
      }),
    );

    await cz.run('prepare-release');

    expect(await loadPackageVersion('packages/consumer/package.json')).toBe('5.0.1');
    expect(await loadArtifact('packages/consumer/CHANGELOG.md')).toContain('@zyplux/util@1.3.0');
  });

  test('18.1.5 directs version lookups to the package publication registry', async ({ cz, shell, tempDir }) => {
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        name: '@zyplux/util',
        publishConfig: { '@zyplux:registry': 'https://npm.pkg.github.com', registry: 'https://registry.npmjs.org' },
        version: '1.2.3',
      }),
    );
    shell.on('pnpm version', { exitCode: 1, stdout: 'Stop after verifying registry selection.' });

    await expect(cz.run('prepare-release')).rejects.toThrow('command failed');

    expect(shell).toHaveRun('pnpm version -r --no-git-checks --config.@zyplux:registry=https://npm.pkg.github.com');
    expect(shell).not.toHaveRunMatching(/pnpm install|uv/);
  });
});
