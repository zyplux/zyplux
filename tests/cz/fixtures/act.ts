import type { FetchFake } from '@zyplux/spectra/fakes/fetch-fake';
import type { CliRunner } from '@zyplux/spectra/helpers/cli-runner';
import type { TempDir } from '@zyplux/spectra/helpers/temp-directory';
import type { ConsoleCapture } from '@zyplux/spectra/reporters/console-capture';

import { runCz } from '@zyplux/cz';
import { DepsCatalogSchema, ManifestSchema, VersionFieldSchema } from '@zyplux/cz/contracts';
import { createCliRunner } from '@zyplux/spectra/helpers/cli-runner';
import { ensure, parseJson, parseToml } from '@zyplux/util';
import { LooseRecordSchema } from '@zyplux/util/contracts';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdir, readFile, symlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));
const configDir = path.join(workspaceRoot, 'packages/tsconfig');
const DEPENDENCY_KEY_PARTS = 2;

export type Catalog = {
  loadRepos: () => Promise<string[]>;
  outPath: string;
  readOutput: (relativePath?: string) => Promise<string>;
  run: (options?: RunCatalogOptions) => Promise<void>;
  stubDepsDev: (sourceRepoByPackage: Record<string, DepsDevSourceRepo>) => void;
  stubNpmRegistry: (repoByName: Record<string, string>) => void;
  stubPypiRegistry: (repoByName: Record<string, string>) => void;
  unresolvedNames: (packageRegistry: 'npm' | 'pypi') => string[];
  writeManifest: (relativePath: string, content: string) => Promise<void>;
};

export type PublishedPackage = { archive: string; dir: string; files: string[]; label: string; targets: string[] };

export type TsconfigPresets = {
  base: EmitPolicy & { composite: boolean };
  baseDeclaresModules: boolean;
  nodePub: EmitPolicy;
  variants: Record<string, { module: string; moduleResolution: string }>;
};

type DepsDevSourceRepo = string | { repo: string; via: 'links' };

type EmitPolicy = {
  declarationMap: boolean;
  emitDeclarationOnly: boolean;
  outDir: string;
  rewriteRelativeImportExtensions: boolean;
  tsBuildInfoFile: string;
};

type RunCatalogOptions = { out?: string };

const escapeRegExp = (text: string) => text.replaceAll(/[$()*+.?[\\\]^{|}]/g, String.raw`\$&`);

const loadRecord = (file: string) => parseJson(readFileSync(file, 'utf8'), LooseRecordSchema);

const listPathTargets = (field: unknown): string[] => {
  if (typeof field === 'string') return field.startsWith('./') && !field.includes('*') ? [field] : [];
  return typeof field !== 'object' || field === null
    ? []
    : Object.values(field).flatMap(value => listPathTargets(value));
};

const depsDevDefaultVersion = () =>
  Response.json({ versions: [{ isDefault: true, versionKey: { version: '1.0.0' } }] });

const depsDevSourceRepoResponse = (sourceRepo: DepsDevSourceRepo) =>
  typeof sourceRepo === 'string'
    ? Response.json({ relatedProjects: [{ projectKey: { id: sourceRepo }, relationType: 'SOURCE_REPO' }] })
    : Response.json({ links: [{ label: 'SOURCE_REPO', url: `https://${sourceRepo.repo}` }] });

export const createCz = () => createCliRunner(runCz);

const loadBoolean = (record: Record<string, unknown>, key: string) => {
  const value = record[key];
  ensure(typeof value === 'boolean', `${key} is not a boolean`);
  return value;
};

const loadEmitPolicy = (preset: Record<string, unknown>) => ({
  declarationMap: loadBoolean(preset, 'declarationMap'),
  emitDeclarationOnly: loadBoolean(preset, 'emitDeclarationOnly'),
  outDir: VersionFieldSchema.parse(preset['outDir']),
  rewriteRelativeImportExtensions: preset['rewriteRelativeImportExtensions'] === true,
  tsBuildInfoFile: VersionFieldSchema.parse(preset['tsBuildInfoFile']),
});

export const loadTsconfigPresets = (): TsconfigPresets => {
  const base = LooseRecordSchema.parse(loadRecord(path.join(configDir, 'base.json'))['compilerOptions']);
  const nodePub = LooseRecordSchema.parse(loadRecord(path.join(configDir, 'node-pub.json'))['compilerOptions']);
  const variants = Object.fromEntries(
    ['bun', 'cfworker', 'node', 'tui', 'web'].map(name => {
      const preset = LooseRecordSchema.parse(loadRecord(path.join(configDir, `${name}.json`))['compilerOptions']);
      return [
        name,
        {
          module: VersionFieldSchema.parse(preset['module']),
          moduleResolution: VersionFieldSchema.parse(preset['moduleResolution']),
        },
      ];
    }),
  );
  return {
    base: { ...loadEmitPolicy(base), composite: loadBoolean(base, 'composite') },
    baseDeclaresModules: 'module' in base || 'moduleResolution' in base,
    nodePub: loadEmitPolicy(nodePub),
    variants,
  };
};

export const loadPublishedPackages = (tempDir: TempDir, label?: string): PublishedPackage[] => {
  const releaseManifest = parseToml(
    readFileSync(path.join(workspaceRoot, 'release-targets.toml'), 'utf8'),
    ManifestSchema,
  );
  const packages: PublishedPackage[] = [];

  for (const target of releaseManifest.target) {
    if (target.kind !== 'npm' || (label !== undefined && target.label !== label)) continue;
    const packageDir = path.join(workspaceRoot, path.dirname(target.version.file));
    const archive = path.join(tempDir.path, `${path.basename(packageDir)}.tgz`);
    const packOutput = execFileSync('pnpm', ['pack', '--out', archive, '--json'], {
      cwd: packageDir,
      encoding: 'utf8',
    });
    const jsonStart = packOutput.lastIndexOf('{\n  "name"');
    ensure(jsonStart !== -1, `pnpm pack returned no JSON for ${target.label}`);
    const pack = parseJson(packOutput.slice(jsonStart), LooseRecordSchema);
    ensure(Array.isArray(pack['files']), `pnpm pack returned no files for ${target.label}`);
    const files = pack['files'].map(file => VersionFieldSchema.parse(LooseRecordSchema.parse(file)['path']));
    const manifest = loadRecord(path.join(packageDir, 'package.json'));
    const publishConfig = LooseRecordSchema.parse(manifest['publishConfig']);
    const targets = [publishConfig['bin'], publishConfig['exports'], publishConfig['imports']].flatMap(field =>
      listPathTargets(field),
    );
    packages.push({ archive, dir: packageDir, files, label: target.label, targets });
  }
  return packages;
};

const createPackageConsumer = async (label: string, dependencyNames: string[], tempDir: TempDir) => {
  const [packed] = loadPublishedPackages(tempDir, label);
  ensure(packed !== undefined, `no packed release target for ${label}`);
  const consumer = path.join(tempDir.path, 'consumer');
  const packageDir = path.join(consumer, 'node_modules', label);
  await mkdir(packageDir, { recursive: true });
  execFileSync('tar', ['-xzf', packed.archive, '--strip-components=1', '-C', packageDir]);
  for (const name of dependencyNames) {
    const dependency = path.join(consumer, 'node_modules', name);
    await mkdir(path.dirname(dependency), { recursive: true });
    await symlink(path.join(packed.dir, 'node_modules', name), dependency, 'dir');
  }
  await tempDir.write('consumer/package.json', '{"type":"module"}');
  return consumer;
};

export const verifySpectraPackage = async (tempDir: TempDir) => {
  const consumer = await createPackageConsumer('@zyplux/spectra', ['vitest'], tempDir);
  await tempDir.write(
    'consumer/vitest.config.mts',
    `import { defineConfig } from 'vitest/config';
import { JournaldReporter } from '@zyplux/spectra/reporters/journald-reporter';
export default defineConfig({ test: { reporters: ['default', new JournaldReporter({ isEnabled: false })] } });`,
  );
  await tempDir.write(
    'consumer/tools.test.mjs',
    `import { expect } from 'vitest';
import { libraryTest as test } from '@zyplux/spectra/library-test-api';
import { pollUntil } from '@zyplux/spectra/helpers/poll-until';
import '@zyplux/spectra/test-matchers';
test('packed fixtures, matchers, and polling work', async ({ tempDir }) => {
  await tempDir.write('marker', 'present');
  expect(tempDir.exists('marker')).toBe(true);
  expect([1, 2]).toHaveNumberOfElements(2);
  expect((await pollUntil(() => true, { timeout: 1000 })).settled).toBe(true);
});`,
  );
  execFileSync(process.execPath, [path.join(consumer, 'node_modules/vitest/vitest.mjs'), 'run'], {
    cwd: consumer,
    stdio: 'pipe',
  });
};

export const verifyUtilPackage = async (tempDir: TempDir) => {
  const consumer = await createPackageConsumer('@zyplux/util', ['smol-toml', 'zod'], tempDir);
  const script = `import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { LapTimer } from '@zyplux/util';
assert.equal(new LapTimer().total, 0);
assert.throws(() => createRequire(import.meta.url).resolve('typescript'), { code: 'MODULE_NOT_FOUND' });`;
  execFileSync(process.execPath, ['--input-type=module', '--eval', script], { cwd: consumer, stdio: 'pipe' });
  await symlink(
    path.join(workspaceRoot, 'node_modules/typescript'),
    path.join(consumer, 'node_modules/typescript'),
    'dir',
  );
  const compilerScript = `import assert from 'node:assert/strict';
import ts from 'typescript';
import { collectModuleReferences } from '@zyplux/util/module-references';
import { findTypeDependencyViolations } from '@zyplux/util/type-dependencies';
const imports = collectModuleReferences(ts.createSourceFile('caller.ts', "import type { Options } from 'provider';", ts.ScriptTarget.Latest, true));
assert.equal(imports[0].specifier, 'provider');
assert.equal(imports[0].isTypeOnly, true);
assert.deepEqual(findTypeDependencyViolations({ imports, packages: [], sharedTypeSurfaces: new Set() }), []);`;
  execFileSync(process.execPath, ['--input-type=module', '--eval', compilerScript], {
    cwd: consumer,
    stdio: 'pipe',
  });
};

export const createCatalog = (cz: CliRunner, tempDir: TempDir, { logLines }: ConsoleCapture, network: FetchFake) => {
  const outPath = path.join(tempDir.path, 'catalog.json');
  const readOutput = (relativePath = 'catalog.json') => readFile(path.join(tempDir.path, relativePath), 'utf8');
  const runGit = (...args: string[]) => {
    execFileSync('git', args, { cwd: tempDir.path, stdio: 'ignore' });
  };
  runGit('init', '--quiet');

  return {
    loadRepos: async () => parseJson(await readOutput(), DepsCatalogSchema),
    outPath,
    readOutput,
    run: async ({ out = 'catalog.json' }: RunCatalogOptions = {}) => {
      await cz.run('deps-catalog', '--dir', tempDir.path, '--out', out);
    },
    stubDepsDev: sourceRepoByPackage => {
      for (const [key, sourceRepo] of Object.entries(sourceRepoByPackage)) {
        const [system, name] = key.split(':', DEPENDENCY_KEY_PARTS);
        const base = `https://api.deps.dev/v3/systems/${system}/packages/${encodeURIComponent(name ?? '')}`;
        network.on(new RegExp(`^${escapeRegExp(base)}$`), () => depsDevDefaultVersion());
        network.on(new RegExp(String.raw`^${escapeRegExp(base)}/versions/1\.0\.0$`), () =>
          depsDevSourceRepoResponse(sourceRepo),
        );
      }
    },
    stubNpmRegistry: repoByName => {
      for (const [name, repo] of Object.entries(repoByName)) {
        network.on(`https://registry.npmjs.org/${name.replace('/', '%2F')}/latest`, () =>
          Response.json({ repository: { url: `git+https://${repo}.git` } }),
        );
      }
    },
    stubPypiRegistry: repoByName => {
      for (const [name, repo] of Object.entries(repoByName)) {
        network.on(`https://pypi.org/pypi/${encodeURIComponent(name)}/json`, () =>
          Response.json({ info: { project_urls: { Source: `https://${repo}` } } }),
        );
      }
    },
    unresolvedNames: packageRegistry => {
      const prefix = `  ${packageRegistry}\t`;
      return logLines.filter(line => line.startsWith(prefix)).map(line => line.slice(prefix.length));
    },
    writeManifest: async (relativePath, content) => {
      await tempDir.write(relativePath, content);
      runGit('add', relativePath);
    },
  } satisfies Catalog;
};
