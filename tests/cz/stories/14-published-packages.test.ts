import { describe, expect, test } from '#fixtures';

describe('14.1 packing release targets', () => {
  test('14.1.1 ships one manifest with resolvable targets in every npm package', ({ publishedPackages }) => {
    for (const publishedPackage of publishedPackages) {
      expect(
        publishedPackage.files.filter(file => file.endsWith('package.json')),
        publishedPackage.label,
      ).toEqual(['package.json']);
      expect(
        publishedPackage.targets.filter(file => !publishedPackage.files.includes(file.replace(/^\.\//, ''))),
        publishedPackage.label,
      ).toEqual([]);
      expect(
        publishedPackage.files.filter(file => file.endsWith('.d.ts.map') || file.endsWith('.tsbuildinfo')),
        publishedPackage.label,
      ).toEqual([]);
    }
  });

  test('14.1.2 filters tests from an isolated installation with only runtime dependencies', async ({
    packagedCz,
    tempDir,
  }) => {
    await tempDir.write('package.json', '{"scripts":{"test":"vitest run"}}');

    await expect(packagedCz.run('test', 'no-matching-tests')).resolves.toBeUndefined();
  });
});

describe('14.2 selecting a module system', () => {
  test('14.2.1 keeps module policy in environment presets', ({ tsconfigPresets }) => {
    expect(tsconfigPresets.baseDeclaresModules).toBe(false);
    expect(tsconfigPresets.variants).toEqual({
      bun: { module: 'Preserve', moduleResolution: 'bundler' },
      cfworker: { module: 'Preserve', moduleResolution: 'bundler' },
      node: { module: 'NodeNext', moduleResolution: 'NodeNext' },
      tui: { module: 'Preserve', moduleResolution: 'bundler' },
      web: { module: 'Preserve', moduleResolution: 'bundler' },
    });
  });
});

describe('14.3 selecting emitted artifacts', () => {
  test('14.3.1 emits declarations for monorepo references and JavaScript only for publishing', ({
    tsconfigPresets,
  }) => {
    expect({ base: tsconfigPresets.base, nodePub: tsconfigPresets.nodePub }).toEqual({
      base: {
        composite: true,
        declarationMap: true,
        emitDeclarationOnly: true,
        outDir: '${configDir}/.tsbuild',
        rewriteRelativeImportExtensions: false,
        tsBuildInfoFile: '${configDir}/.tsbuild/tsconfig.tsbuildinfo',
      },
      nodePub: {
        declarationMap: false,
        emitDeclarationOnly: false,
        outDir: '${configDir}/dist',
        rewriteRelativeImportExtensions: true,
        tsBuildInfoFile: '${configDir}/.tsbuild/tsconfig-pub.tsbuildinfo',
      },
    });
  });
});
