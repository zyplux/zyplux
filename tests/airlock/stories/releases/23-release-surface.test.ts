import { vi } from 'vitest';

import { describe, expect, test } from './releases.ts';

const DONE = { message: "every published target's version tracks its surface", status: 'pass' };
const buildActionRelease = (tag: string, isDraft = false, isPrerelease = false) => ({
  draft: isDraft,
  prerelease: isPrerelease,
  tag_name: tag,
});

describe('23.1 validating release targets and versions', () => {
  test.for(['not = valid = toml', '', 'scope = ""', 'scope = 1', 'scope = "@demo"\nutil = 1'])(
    '23.1.1 rejects malformed manifests (%j)',
    async (manifest, { checkSurface, tempDir }) => {
      await tempDir.write('airlock-targets.toml', manifest);
      expect(await checkSurface()).toEqual([expect.objectContaining({ status: 'error' })]);
    },
  );

  test('23.1.2 accepts a scope with no targets', async ({ checkSurface, tempDir }) => {
    await tempDir.write('airlock-targets.toml', 'scope = "@zyplux"');
    expect(await checkSurface()).toEqual([DONE]);
  });

  test.for(['invalid json', '{}', '{"version":42}', '{"version":"invalid"}', '{"version":"1.2.3-beta.1"}'])(
    '23.1.3 rejects missing or invalid versions (%j)',
    async (manifest, { checkSurface, tempDir }) => {
      await tempDir.write('packages/util/package.json', manifest);
      expect(await checkSurface()).toEqual([expect.objectContaining({ status: 'fail' })]);
    },
  );

  test('23.1.4 reports missing version files', async ({ checkSurface, configureTarget }) => {
    await configureTarget('npm', 'version = { file = "missing.json", json = "version" }');
    const findings = await checkSurface();
    expect(findings).toEqual([expect.objectContaining({ status: 'fail' })]);
    expect(findings[0]?.message).toContain('missing.json');
  });

  test('23.1.5 reads native Python versions with the configured regex', async ({
    checkSurface,
    configureTarget,
    setPublishedVersion,
  }) => {
    await configureTarget(
      'npm',
      `kind = "pypi"\nlabel = "zyplux-cerberus"\nversion = { file = "apps/cerberus/pyproject.toml", regex = '^version = "([^"]+)"' }`,
    );
    setPublishedVersion('2.3.3');
    expect(await checkSurface()).toContainEqual({
      message: 'zyplux-cerberus: 2.3.4 is ahead of published 2.3.3',
      status: 'pass',
    });
  });

  test('23.1.6 validates every target when one version is invalid', async ({ checkSurface, loadArtifact, tempDir }) => {
    await tempDir.write('packages/util/package.json', JSON.stringify({ version: '1.2.4' }));
    await tempDir.write(
      'airlock-targets.toml',
      `${await loadArtifact('airlock-targets.toml')}\n[broken]\nkind = "npm"\nsurface = []\nversion = { file = "missing.json", json = "version" }\n`,
    );
    const findings = await checkSurface();
    expect(findings).toEqual([
      { message: '@zyplux/util: 1.2.4 is ahead of published 1.2.3', status: 'pass' },
      expect.objectContaining({ status: 'fail' }),
    ]);
    expect(findings.at(-1)?.message).toContain('@zyplux/broken');
  });
});

describe('23.2 requiring one-step release bumps', () => {
  test.for(['1.2.4', '1.3.0', '2.0.0'])(
    '23.2.1 accepts a single patch minor or major bump (%s)',
    async (version, { checkSurface, tempDir }) => {
      await tempDir.write('packages/util/package.json', JSON.stringify({ version }));
      expect(await checkSurface()).toEqual([
        { message: `@zyplux/util: ${version} is ahead of published 1.2.3`, status: 'pass' },
        DONE,
      ]);
    },
  );

  test.for(['1.2.5', '1.4.0', '3.0.0', '1.3.1'])(
    '23.2.2 rejects skipped bumps (%s)',
    async (version, { checkSurface, tempDir }) => {
      await tempDir.write('packages/util/package.json', JSON.stringify({ version }));
      expect(await checkSurface()).toEqual([
        {
          message: `@zyplux/util: version ${version} skips ahead of published 1.2.3 — bump one step (1.2.4, 1.3.0, or 2.0.0)`,
          status: 'fail',
        },
      ]);
    },
  );

  test('23.2.3 rejects versions below the published version', async ({ checkSurface, setPublishedVersion }) => {
    setPublishedVersion('1.10.0');
    expect(await checkSurface()).toEqual([
      { message: '@zyplux/util: version 1.2.3 is below published 1.10.0', status: 'fail' },
    ]);
  });

  test('23.2.4 permits an initial release', async ({ checkSurface, setPublishedVersion }) => {
    setPublishedVersion();
    expect(await checkSurface()).toEqual([{ message: '@zyplux/util: not yet released', status: 'pass' }, DONE]);
  });

  test('23.2.5 accepts published versions with unchanged surfaces', async ({ checkSurface }) => {
    expect(await checkSurface()).toEqual([DONE]);
  });

  test('23.2.6 rejects changes to an already published version', async ({ checkSurface, shell }) => {
    shell.on('git diff --name-only util-v1.2.3 -- packages/util/src', 'packages/util/src/index.ts');
    expect(await checkSurface()).toEqual([
      {
        message: '@zyplux/util: surface changed since util-v1.2.3 but version is still 1.2.3 — bump it (e.g. 1.2.4)',
        status: 'fail',
      },
    ]);
  });

  test('23.2.7 reports unavailable release history', async ({ checkSurface, shell }) => {
    shell.on('git diff', { exitCode: 1, stdout: 'missing tag' });
    const findings = await checkSurface();
    expect(findings).toEqual([expect.objectContaining({ status: 'error' })]);
    expect(findings[0]?.message).toContain('cannot diff against util-v1.2.3');
  });
});

describe('23.3 comparing pull request baselines', () => {
  test.for([
    { base: '1.2.4', current: '1.2.4', published: '1.2.3' },
    { base: '2.0.0', current: '2.0.0', published: '1.2.3' },
    { base: '1.2.3', current: '1.2.3', published: undefined },
  ])(
    '23.3.1 permits repairs to unpublished target branch versions (%j)',
    async ({ base, current, published }, { checkSurface, setBaseVersion, setPublishedVersion, shell, tempDir }) => {
      await setBaseVersion(base);
      setPublishedVersion(published);
      shell.on('git diff', 'packages/util/src/index.ts');
      await tempDir.write('packages/util/package.json', JSON.stringify({ version: current }));
      expect(await checkSurface('origin/main')).toEqual([DONE]);
      expect(shell).not.toHaveRunMatching('git diff');
    },
  );

  test.for([
    { base: '1.2.4', baseline: 'origin/main (1.2.4)', current: '1.2.5', published: '1.2.3' },
    { base: '1.2.4', baseline: 'origin/main (1.2.4)', current: '1.3.0', published: '1.2.3' },
    { base: '1.2.3', baseline: 'published 1.2.4', current: '1.2.5', published: '1.2.4' },
    { base: '1.2.3', baseline: 'origin/main (1.2.3)', current: '1.2.4', published: undefined },
  ])(
    '23.3.2 uses the newer published or target branch baseline (%j)',
    async ({ base, baseline, current, published }, { checkSurface, setBaseVersion, setPublishedVersion, tempDir }) => {
      await setBaseVersion(base);
      setPublishedVersion(published);
      await tempDir.write('packages/util/package.json', JSON.stringify({ version: current }));
      expect(await checkSurface('origin/main')).toEqual([
        { message: `@zyplux/util: ${current} is ahead of ${baseline}`, status: 'pass' },
        DONE,
      ]);
    },
  );

  test('23.3.3 rejects regressions against an unpublished target branch version', async ({
    checkSurface,
    setBaseVersion,
  }) => {
    await setBaseVersion('1.2.4');
    expect(await checkSurface('origin/main')).toEqual([
      { message: '@zyplux/util: version must not decrease from origin/main (1.2.4)', status: 'fail' },
    ]);
  });

  test('23.3.4 rejects skipped bumps before first publication', async ({
    checkSurface,
    setBaseVersion,
    setPublishedVersion,
    tempDir,
  }) => {
    await setBaseVersion('1.2.3');
    setPublishedVersion();
    await tempDir.write('packages/util/package.json', JSON.stringify({ version: '9.0.0' }));
    expect(await checkSurface('origin/main')).toEqual([
      {
        message:
          '@zyplux/util: version 9.0.0 skips ahead of origin/main (1.2.3) — bump one step (1.2.4, 1.3.0, or 2.0.0)',
        status: 'fail',
      },
    ]);
  });

  test('23.3.5 allows targets introduced by the pull request', async ({
    checkSurface,
    setBaseVersion,
    setPublishedVersion,
  }) => {
    await setBaseVersion();
    setPublishedVersion();
    expect(await checkSurface('origin/main')).toEqual([
      { message: '@zyplux/util: not yet released', status: 'pass' },
      DONE,
    ]);
  });

  test.for(['invalid json', '{}', '{"version":"invalid"}'])(
    '23.3.6 rejects malformed target branch versions (%s)',
    async (manifest, { checkSurface, setBaseVersion, shell }) => {
      await setBaseVersion('1.2.3');
      shell.on('git show origin/main:packages/util/package.json', manifest);
      const findings = await checkSurface('origin/main');
      expect(findings).toEqual([expect.objectContaining({ status: 'error' })]);
      expect(findings[0]?.message).toContain('cannot compare the target branch origin/main');
    },
  );

  test('23.3.7 rejects unavailable target branch history', async ({ checkSurface, shell }) => {
    shell.on('git ls-tree', { exitCode: 1, stdout: 'missing ref' });
    expect(await checkSurface('origin/main')).toEqual([expect.objectContaining({ status: 'error' })]);
  });

  test('23.3.8 reads the base version with its own extractor and path', async ({
    checkSurface,
    configureTarget,
    setBaseVersion,
    tempDir,
  }) => {
    await setBaseVersion('1.2.3');
    await configureTarget('npm', 'version = { file = "packages/moved/package.json", json = "metadata.version" }');
    await tempDir.write('packages/moved/package.json', JSON.stringify({ metadata: { version: '1.2.4' } }));
    expect(await checkSurface('origin/main')).toEqual([
      { message: '@zyplux/util: 1.2.4 is ahead of published 1.2.3', status: 'pass' },
      DONE,
    ]);
  });

  test('23.3.9 reports missing base version files', async ({ checkSurface, setBaseVersion, shell }) => {
    await setBaseVersion('1.2.3');
    shell.on('git ls-tree --name-only origin/main -- packages/util/package.json', '');
    const findings = await checkSurface('origin/main');
    expect(findings).toEqual([expect.objectContaining({ status: 'error' })]);
    expect(findings[0]?.message).toContain('version file packages/util/package.json is missing');
  });

  test('23.3.10 distinguishes targets sharing a version file', async ({
    checkSurface,
    loadArtifact,
    setBaseVersion,
    setPublishedVersion,
    shell,
  }) => {
    await setBaseVersion('9.0.0');
    const manifest = await loadArtifact('airlock-targets.toml');
    shell.on('git show origin/main:airlock-targets.toml', manifest.replace('[util]', '[other]'));
    setPublishedVersion();
    expect(await checkSurface('origin/main')).toEqual([
      { message: '@zyplux/util: not yet released', status: 'pass' },
      DONE,
    ]);
  });

  test('23.3.11 uses the GitHub target branch by default', async ({ checkSurface, env, setBaseVersion }) => {
    env.set('GITHUB_BASE_REF', 'main');
    await setBaseVersion('1.2.4');
    expect(await checkSurface()).toEqual([
      { message: '@zyplux/util: version must not decrease from origin/main (1.2.4)', status: 'fail' },
    ]);
  });
});

describe('23.4 reading published release versions', () => {
  test.for([
    { registry: 'https://registry.npmjs.org/' },
    { registry: 'https://npm.pkg.github.com/' },
    { '@zyplux:registry': 'https://npm.pkg.github.com/', registry: 'https://registry.npmjs.org' },
  ])('23.4.1 follows scoped publication registries (%j)', async (publishConfig, { checkSurface, env, tempDir }) => {
    env.set('NODE_AUTH_TOKEN', 'read-token');
    await tempDir.write('packages/util/package.json', JSON.stringify({ publishConfig, version: '1.2.3' }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    expect(await checkSurface()).toEqual([DONE]);
    const registry = publishConfig['@zyplux:registry'] ?? publishConfig.registry;
    expect(fetchSpy).toHaveBeenCalledWith(
      `${registry.replace(/\/$/u, '')}/%40zyplux%2Futil`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  test('23.4.2 rejects missing private registry credentials', async ({ checkSurface, env, tempDir }) => {
    env.set('NODE_AUTH_TOKEN', '');
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({ publishConfig: { registry: 'https://npm.pkg.github.com' }, version: '1.2.3' }),
    );
    const findings = await checkSurface();
    expect(findings).toEqual([expect.objectContaining({ status: 'error' })]);
    expect(findings[0]?.message).toContain('GitHub Packages requires authentication');
  });

  test.for([{ registry: 'https://example.com' }, { registry: 42 }, 'invalid'])(
    '23.4.3 rejects unsupported publication configuration (%j)',
    async (publishConfig, { checkSurface, tempDir }) => {
      await tempDir.write('packages/util/package.json', JSON.stringify({ publishConfig, version: '1.2.3' }));
      expect(await checkSurface()).toEqual([expect.objectContaining({ status: 'error' })]);
    },
  );

  test.for([
    { metadata: {}, status: 200 },
    { metadata: { 'dist-tags': { latest: 'invalid' } }, status: 200 },
    { metadata: {}, status: 403 },
    { metadata: {}, status: 502 },
  ])('23.4.4 reports registry failures as errors (%j)', async ({ metadata, status }, { checkSurface, network }) => {
    network.on('https://registry.npmjs.org/', () => Response.json(metadata, { status }));
    expect(await checkSurface()).toEqual([expect.objectContaining({ status: 'error' })]);
  });

  test('23.4.5 compares stable action releases across all pages', async ({
    checkSurface,
    configureTarget,
    shell,
    tempDir,
  }) => {
    await configureTarget('npm', 'kind = "action"\nrepository = "zyplux/zyplux"');
    await tempDir.write('packages/util/package.json', JSON.stringify({ version: '1.10.1' }));
    shell.on(
      'gh api --paginate --slurp',
      JSON.stringify([
        [buildActionRelease('other-v99.0.0'), buildActionRelease('util-v1.9.0')],
        [
          buildActionRelease('util-v1.10.0'),
          buildActionRelease('util-v1.11.0', true),
          buildActionRelease('util-v1.12.0', false, true),
          buildActionRelease('util-v1.13.0-beta.1'),
          buildActionRelease('util-vinvalid'),
        ],
      ]),
    );
    expect(await checkSurface()).toEqual([
      { message: '@zyplux/util: 1.10.1 is ahead of published 1.10.0', status: 'pass' },
      DONE,
    ]);
    expect(shell).not.toHaveRunMatching('git ls-remote');
  });

  test('23.4.6 selects stable numeric container tags', async ({ checkSurface, configureTarget, network }) => {
    await configureTarget('npm', 'kind = "ghcr"\nlabel = "ghcr.io/zyplux/ci"');
    network.on('https://ghcr.io/v2/', () => Response.json({ tags: ['latest', '1.2.2', '1.2.4-beta.1'] }));
    expect(await checkSurface()).toEqual([
      { message: 'ghcr.io/zyplux/ci: 1.2.3 is ahead of published 1.2.2', status: 'pass' },
      DONE,
    ]);
  });

  test('23.4.7 prints readable findings without json mode', async ({ logs, surfaceCli }) => {
    await surfaceCli.run('check-surface');
    expect(logs.logLines).toEqual([`pass: ${DONE.message}`]);
  });
});

describe('23.5 reusing GitHub credentials for private registry reads', () => {
  test.for(['GH_TOKEN', 'GITHUB_TOKEN', 'gh login'])(
    '23.5.1 reads private npm metadata using %s without manual NODE_AUTH_TOKEN exports',
    async (source, { checkSurface, env, shell, tempDir }) => {
      if (source === 'gh login') shell.on('gh auth token', 'saved-token');
      else env.set(source, 'saved-token');
      await tempDir.write(
        'packages/util/package.json',
        JSON.stringify({
          publishConfig: { registry: 'https://npm.pkg.github.com' },
          version: '1.2.3',
        }),
      );
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      expect(await checkSurface()).toEqual([DONE]);
      expect(fetchSpy).toHaveBeenCalledWith('https://npm.pkg.github.com/%40zyplux%2Futil', {
        headers: { Authorization: 'Bearer saved-token' },
        method: 'GET',
      });
      if (source !== 'gh login') expect(shell).not.toHaveRunMatching('gh auth token');
    },
  );

  test('23.5.2 authenticates private container reads with the saved login and its actor', async ({
    checkSurface,
    configureTarget,
    network,
    shell,
  }) => {
    await configureTarget('npm', 'kind = "ghcr"\nlabel = "ghcr.io/zyplux/ci"');
    shell.on('gh auth token', 'saved-token');
    network.on('https://api.github.com/user', () => Response.json({ login: 'reader' }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    expect(await checkSurface()).toEqual([DONE]);
    expect(fetchSpy).toHaveBeenCalledWith('https://api.github.com/user', {
      headers: { Authorization: 'Bearer saved-token', 'User-Agent': 'zyplux-airlock' },
      method: 'GET',
    });
    expect(fetchSpy).toHaveBeenCalledWith('https://ghcr.io/token?service=ghcr.io&scope=repository:zyplux/ci:pull', {
      headers: { Authorization: `Basic ${Buffer.from('reader:saved-token').toString('base64')}` },
      method: 'GET',
    });
  });

  test('23.5.3 preserves explicitly supplied credentials and reports denied access', async ({
    checkSurface,
    env,
    network,
    shell,
    tempDir,
  }) => {
    env.set('NODE_AUTH_TOKEN', 'explicit-token');
    env.set('GH_TOKEN', 'other-token');
    shell.on('gh auth token', 'saved-token');
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        publishConfig: { registry: 'https://npm.pkg.github.com' },
        version: '1.2.3',
      }),
    );
    network.on('https://npm.pkg.github.com/', () => new Response(undefined, { status: 403 }));
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    expect(await checkSurface()).toEqual([expect.objectContaining({ status: 'error' })]);
    expect(fetchSpy).toHaveBeenCalledWith('https://npm.pkg.github.com/%40zyplux%2Futil', {
      headers: { Authorization: 'Bearer explicit-token' },
      method: 'GET',
    });
    expect(shell).not.toHaveRunMatching('gh auth token');
  });
});
