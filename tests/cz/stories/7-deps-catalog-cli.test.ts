import type { TempDir } from '#fixtures';

import { describe, expect, test } from '#fixtures';

const JSON_INDENT = 2;

const NO_DEPS_MANIFEST = JSON.stringify({ name: 'scratch-app' });
const TWO_DEPS_MANIFEST = JSON.stringify({ dependencies: { react: '^19', zod: '^3' }, name: 'scratch-app' });

describe('7.1 writing the resolved repos to the output file', () => {
  test('7.1.1 writes the sorted repos as indented json and reports the count', async ({ catalog, logs }) => {
    await catalog.writeManifest('package.json', TWO_DEPS_MANIFEST);
    catalog.stubDepsDev({
      'npm:react': 'github.com/facebook/react',
      'npm:zod': 'github.com/colinhacks/zod',
    });

    await catalog.run();

    const repos = ['https://github.com/colinhacks/zod', 'https://github.com/facebook/react'];
    await expect(catalog.readOutput()).resolves.toBe(`${JSON.stringify(repos, undefined, JSON_INDENT)}\n`);
    expect(logs).toHaveLogged(`Wrote 2 source repositories to ${catalog.outPath}`);
  });

  test('7.1.2 reports unresolved dependencies alongside the written count', async ({ catalog, logs }) => {
    await catalog.writeManifest('package.json', TWO_DEPS_MANIFEST);

    await catalog.run();

    expect(logs).toHaveLogged('Unresolved (2) — no source repo found:');
    expect(logs).toHaveLogged('  npm\treact');
    expect(logs).toHaveLogged('  npm\tzod');
  });
});

type OutPathCase = [shape: string, buildOut: (tempDir: TempDir) => string, expectedOutputPath: string];

const outPathCases: OutPathCase[] = [
  ['1 joins a relative --out under --dir', () => 'nested/catalog.json', 'nested/catalog.json'],
  ['2 uses an absolute --out as-is', tempDir => `${tempDir.path}/elsewhere.json`, 'elsewhere.json'],
];

describe('7.2 resolving the output path', () => {
  test.for(outPathCases)('7.2.%s', async ([, buildOut, expectedOutputPath], { catalog, tempDir }) => {
    await catalog.writeManifest('package.json', NO_DEPS_MANIFEST);

    await catalog.run({ out: buildOut(tempDir) });

    await expect(catalog.readOutput(expectedOutputPath)).resolves.toBe('[]\n');
  });
});
