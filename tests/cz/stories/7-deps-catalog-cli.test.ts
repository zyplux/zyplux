import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { describe, expect, notFoundResponse, test } from '#fixtures';

type FetchRoute = (url: string) => Response;

const JSON_INDENT = 2;

const NO_DEPS_MANIFEST = JSON.stringify({ name: 'scratch-app' });
const TWO_DEPS_MANIFEST = JSON.stringify({ dependencies: { react: '^19', zod: '^3' }, name: 'scratch-app' });

const sourceRepoByName = new Map([
  ['react', 'github.com/facebook/react'],
  ['zod', 'github.com/colinhacks/zod'],
]);

const depsDevDefaultVersion = () =>
  Response.json({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });

const resolveViaDepsDev: FetchRoute = url => {
  const match = /api\.deps\.dev\/v3\/systems\/npm\/packages\/([^/]+)(\/versions\/.+)?$/.exec(url);
  if (match === null) return notFoundResponse();
  const [, encodedName, versionPath] = match;
  const repo = encodedName === undefined ? undefined : sourceRepoByName.get(decodeURIComponent(encodedName));
  if (repo === undefined) return notFoundResponse();
  return versionPath === undefined
    ? depsDevDefaultVersion()
    : Response.json({ relatedProjects: [{ projectKey: { id: repo }, relationType: 'SOURCE_REPO' }] });
};

describe('7.1 writing the resolved repos to the output file', () => {
  test('7.1.1 writes the sorted repos as indented json and reports the count', async ({
    catalog,
    logs,
    network,
    tempDir,
  }) => {
    await catalog.writeManifest('package.json', TWO_DEPS_MANIFEST);
    network.otherwise(resolveViaDepsDev);

    await catalog.run();

    const repos = ['https://github.com/colinhacks/zod', 'https://github.com/facebook/react'];
    const written = await readFile(path.join(tempDir.path, 'catalog.json'), 'utf8');
    expect(written).toBe(`${JSON.stringify(repos, undefined, JSON_INDENT)}\n`);
    expect(logs.logLines).toContain(`Wrote 2 source repositories to ${path.join(tempDir.path, 'catalog.json')}`);
  });

  test('7.1.2 reports unresolved dependencies alongside the written count', async ({ catalog, logs, network }) => {
    await catalog.writeManifest('package.json', TWO_DEPS_MANIFEST);
    network.otherwise(() => notFoundResponse());

    await catalog.run();

    expect(logs.logLines).toContain('Unresolved (2) — no source repo found:');
    expect(logs.logLines).toContain('  npm\treact');
    expect(logs.logLines).toContain('  npm\tzod');
  });
});

describe('7.2 resolving the output path', () => {
  test('7.2.1 joins a relative --out under --dir', async ({ catalog, tempDir }) => {
    await catalog.writeManifest('package.json', NO_DEPS_MANIFEST);

    await catalog.run({ out: 'nested/catalog.json' });

    await expect(readFile(path.join(tempDir.path, 'nested/catalog.json'), 'utf8')).resolves.toBe('[]\n');
  });

  test('7.2.2 uses an absolute --out as-is', async ({ catalog, tempDir }) => {
    await catalog.writeManifest('package.json', NO_DEPS_MANIFEST);
    const absoluteOut = path.join(tempDir.path, 'elsewhere.json');

    await catalog.run({ out: absoluteOut });

    await expect(readFile(absoluteOut, 'utf8')).resolves.toBe('[]\n');
  });
});
