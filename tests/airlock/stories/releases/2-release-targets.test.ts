// unparametrized
import { vi } from 'vitest';

import { describe, expect, test } from './releases.ts';

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
    planReleases,
    release,
  }) => {
    release.stageAllPublished();

    expect(await planReleases()).toEqual([]);
  });
});

describe('2.2 reading a version whose regex does not match its source file', () => {
  test('2.2.1 rejects reading a version whose regex does not match the file', async ({ airlock, tempDir }) => {
    await tempDir.write('release-targets.toml', BROKEN_TARGET_MANIFEST);
    await tempDir.write('VERSION', '1.2.3\n');

    await expect(airlock.run('assert-tag-version', 'broken-v1.2.3')).rejects.toThrow(
      'could not read version from VERSION',
    );
  });
});

describe('2.3 checking whether the ghcr image target is published', () => {
  test('2.3.1 treats a failed registry auth handshake as not published', async ({
    planReleases,
    registries,
    release,
    shell,
  }) => {
    release.stageAllPublished();
    registries.denyGhcrAuth();
    shell.on('gh api graphql', '{"data":{"repository":{"release":{"id":"release-id"}}}}');

    expect(await planReleases()).toEqual([expect.objectContaining({ kind: 'ghcr', tags: ['ci-image-v3.4.5'] })]);
  });

  test.for([
    { ghToken: 'read-token', nodeToken: '' },
    { ghToken: '', nodeToken: 'read-token' },
  ])(
    '2.3.2 authenticates private image probes and propagates registry failures (%j)',
    async ({ ghToken, nodeToken }, { airlock, env, network, registries }) => {
      registries.setPublished({ ghcrPublished: true });
      env.set('GH_TOKEN', ghToken);
      env.set('NODE_AUTH_TOKEN', nodeToken);
      env.set('GITHUB_ACTOR', 'bot');
      network.on('https://ghcr.io/token', () => Response.json({ token: 'private-token' }));
      network.on('https://ghcr.io/v2/', () => new Response(undefined, { status: 403 }));
      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      await expect(airlock.run('publish-tagged-target', 'ci-image-v3.4.5')).rejects.toThrow('403');
      expect(fetchSpy).toHaveBeenCalledWith('https://ghcr.io/token?service=ghcr.io&scope=repository:zyplux/ci:pull', {
        headers: { Authorization: 'Basic Ym90OnJlYWQtdG9rZW4=' },
        method: 'GET',
      });
    },
  );
});

describe("2.4 conforming the repo's own release manifest", () => {
  test('2.4.1 loads a version for every target declared in release-targets.toml', async ({
    airlock,
    liveWorkspace,
    logs,
    repo,
  }) => {
    repo.setRoot(liveWorkspace.root);

    await airlock.run('list-prepared-releases');

    const labels = await liveWorkspace.targetLabels();
    expect(labels).not.toHaveLength(0);
    for (const label of labels) {
      expect(logs.logLines).toContainEqual(expect.stringContaining(`"label":"${label}"`));
    }
  });
});
