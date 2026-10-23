import { describe, expect, test } from './releases.ts';

describe('21.1 planning isolated publication batches', () => {
  test('21.1.1 separates publication kinds and groups npm packages', async ({ planReleases, registries }) => {
    registries.setPublished({});
    expect(await planReleases()).toEqual([
      { environment: 'npm', id: 'npm', kind: 'npm', runner: 'ubuntu-latest', tags: ['util-v1.2.3'] },
      { environment: 'pypi', id: 'pypi-cerberus', kind: 'pypi', runner: 'ubuntu-latest', tags: ['cerberus-v2.3.4'] },
      { environment: 'ghcr', id: 'ghcr-ci-image', kind: 'ghcr', runner: 'ubuntu-latest', tags: ['ci-image-v3.4.5'] },
    ]);
  });

  test('21.1.2 honors target environments', async ({ configureTarget, planReleases, registries }) => {
    registries.setPublished({});
    await configureTarget('pypi', 'environment = "python-production"');
    expect(await planReleases()).toContainEqual(
      expect.objectContaining({
        environment: 'python-production',
        id: 'pypi-cerberus',
        tags: ['cerberus-v2.3.4'],
      }),
    );
  });

  test('21.1.3 plans action alias repair independently', async ({ actionRelease, planReleases }) => {
    actionRelease.setPublished(['setup-pm-v1.0.0']);
    expect(await planReleases()).toEqual([
      {
        environment: 'actions',
        id: 'action-setup-pm',
        kind: 'action',
        runner: 'ubuntu-latest',
        tags: ['setup-pm-v1.0.0'],
      },
    ]);
  });
});

describe('21.2 executing the selected publication batch', () => {
  test('21.2.1 publishes only the selected npm target and writes its summary', async ({
    airlock,
    env,
    loadArtifact,
    planReleases,
    registries,
    repo,
    shell,
    tempDir,
  }) => {
    repo.setHeadSha('reviewed-sha');
    registries.setPublished({});
    const [batch] = await planReleases();
    registries.setPublished({ npmPublished: true });
    env.set('GITHUB_STEP_SUMMARY', `${tempDir.path}/summary.md`);
    shell.on('pnpm --filter', '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    await airlock.run('publish', '--batch', JSON.stringify(batch));
    expect(shell).toHaveRun(
      'pnpm --filter @zyplux/util publish --recursive --report-summary --publish-wait-timeout 600000',
    );
    expect(shell).not.toHaveRunMatching(/uv|podman/);
    expect(await loadArtifact('summary.md')).toContain('npm: published');
    expect(await loadArtifact('summary.md')).toContain('util-v1.2.3');
  });

  test('21.2.2 honors a single-tag plan when several npm targets exist', async ({
    airlock,
    loadArtifact,
    planReleases,
    registries,
    repo,
    shell,
    tempDir,
  }) => {
    const manifest = await loadArtifact('airlock-targets.toml');
    await tempDir.write(
      'airlock-targets.toml',
      `${manifest}\n[extra]\nkind = "npm"\nsurface = []\nversion = { file = "packages/extra/package.json", json = "version" }\n`,
    );
    await tempDir.write('packages/extra/package.json', '{"name":"@zyplux/extra","version":"1.2.3"}');
    await tempDir.write('packages/extra/CHANGELOG.md', '# Extra\n\n## 1.2.3\n\n- Publish extra.\n');
    const batches = await planReleases();
    expect(batches[0]?.tags).toEqual(['util-v1.2.3', 'extra-v1.2.3']);
    const [batch] = await planReleases('util-v1.2.3');
    registries.setPublished({ npmPublished: true });
    repo.setHeadSha('reviewed-sha');
    shell.on('pnpm --filter', '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    await airlock.run('publish', '--batch', JSON.stringify(batch));
    expect(shell).not.toHaveRunMatching(/pnpm .*@zyplux\/extra|gh release create extra-v/);
  });

  test('21.2.3 reports a failed npm batch without creating GitHub releases', async ({
    airlock,
    env,
    loadArtifact,
    planReleases,
    registries,
    shell,
    tempDir,
  }) => {
    registries.setPublished({});
    const [batch] = await planReleases();
    env.set('GITHUB_STEP_SUMMARY', `${tempDir.path}/summary.md`);
    shell.on('pnpm --filter', { exitCode: 1, stdout: 'registry unavailable' });
    await expect(airlock.run('publish', '--batch', JSON.stringify(batch))).rejects.toThrow('command failed');
    expect(await loadArtifact('summary.md')).toContain('npm: failed');
    expect(shell).not.toHaveRunMatching('gh release create');
  });

  test.for([
    { environment: 'wrong' },
    { id: 'wrong' },
    { kind: 'pypi' },
    { tags: ['util-v0.0.1'] },
    { tags: ['util-v1.2.3', 'cerberus-v2.3.4'] },
  ])(
    '21.2.4 rejects batches that disagree with the checkout (%j)',
    async (override, { airlock, planReleases, registries, shell }) => {
      registries.setPublished({});
      const [batch] = await planReleases();
      await expect(airlock.run('publish', '--batch', JSON.stringify({ ...batch, ...override }))).rejects.toThrow();
      expect(shell).not.toHaveRunMatching(/pnpm publish|pnpm --filter|uv|podman/);
    },
  );

  test('21.2.5 publishes a Python batch through uv', async ({ airlock, planReleases, registries, repo, shell }) => {
    registries.setPublished({});
    repo.setHeadSha('reviewed-sha');
    const batches = await planReleases();
    const batch = batches.find(batch => batch.kind === 'pypi');
    shell.on('uv build', '');
    shell.on('uv publish', '');
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');
    await airlock.run('publish', '--batch', JSON.stringify(batch));
    expect(shell).toHaveRunMatching('uv publish');
    expect(shell).toHaveRunMatching('gh release create cerberus-v2.3.4');
  });
});

describe('21.3 selecting incomplete releases', () => {
  test('21.3.1 plans no batches when every release is complete', async ({ planReleases, release }) => {
    release.stageAllPublished();
    expect(await planReleases()).toEqual([]);
  });

  test('21.3.2 retries a missing artifact whose GitHub release exists', async ({ planReleases, release }) => {
    release.stagePendingCerberus();
    expect(await planReleases()).toEqual([expect.objectContaining({ kind: 'pypi', tags: ['cerberus-v2.3.4'] })]);
  });

  test('21.3.3 selects published artifacts with missing GitHub releases', async ({ planReleases, release, shell }) => {
    release.stageAllPublished();
    shell.on(/tag=util-v1\.2\.3 /u, '{"data":{"repository":{"release":null}}}');
    expect(await planReleases()).toEqual([expect.objectContaining({ kind: 'npm', tags: ['util-v1.2.3'] })]);
  });

  test('21.3.4 rejects a tag that does not match a configured version', async ({ planReleases }) => {
    await expect(planReleases('util-v1.2.2')).rejects.toThrow("no configured release target matches 'util-v1.2.2'");
  });

  test('21.3.5 plans no batches for a repository with no release targets', async ({ planReleases, tempDir }) => {
    await tempDir.write('airlock-targets.toml', 'scope = "@zyplux"\n');
    expect(await planReleases()).toEqual([]);
  });

  test('21.3.6 propagates release lookup failures without emitting a plan', async ({
    logs,
    planReleases,
    release,
    shell,
  }) => {
    release.stageAllPublished();
    shell.on('gh api graphql', { exitCode: 1, stdout: 'authentication failed' });
    await expect(planReleases()).rejects.toMatchObject({ exitCode: 1 });
    expect(logs.logLines).toEqual([]);
  });
});
