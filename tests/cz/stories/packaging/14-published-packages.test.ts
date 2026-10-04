import { describe, expect, test } from './packaging.ts';

describe('14.1 packing release targets', () => {
  test('14.1.1 passes Publint for every built npm archive', ({ verifyPublishedPackages }) => {
    verifyPublishedPackages();
  });

  test('14.1.2 supports util imports with an optional TypeScript peer', async ({ verifyUtilPackage }) => {
    await verifyUtilPackage();
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
