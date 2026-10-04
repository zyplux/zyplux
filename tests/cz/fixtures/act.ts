import type { CliRunner } from '@zyplux/tests-fixtures/cli';
import type { ConsoleCapture } from '@zyplux/tests-fixtures/console';
import type { FetchFake } from '@zyplux/tests-fixtures/fetch';
import type { TempDir } from '@zyplux/tests-fixtures/fs';

import { runCz } from '@zyplux/cz';
import { DepsCatalogSchema, ManifestSchema, VersionFieldSchema } from '@zyplux/cz/contracts';
import { createCliRunner } from '@zyplux/tests-fixtures/cli';
import { ensure, parseJson, parseToml } from '@zyplux/util';
import { LooseRecordSchema } from '@zyplux/util/contracts';
import { execFile, execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdir, readFile, symlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

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

export type PublishedPackage = { files: string[]; label: string; targets: string[] };

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

export const createPackagedCz = async (tempDir: TempDir) => {
  const sourceDir = path.join(workspaceRoot, 'apps/cz');
  const archive = path.join(tempDir.path, 'cz.tgz');
  execFileSync('pnpm', ['pack', '--out', archive], { cwd: sourceDir, stdio: 'pipe' });
  execFileSync('tar', ['-xzf', archive, '-C', tempDir.path]);
  const packageDir = path.join(tempDir.path, 'package');
  const manifest = loadRecord(path.join(packageDir, 'package.json'));
  const dependencyNames = Object.keys(LooseRecordSchema.parse(manifest['dependencies']));
  for (const name of dependencyNames) {
    const dependency = path.join(packageDir, 'node_modules', name);
    await mkdir(path.dirname(dependency), { recursive: true });
    await symlink(path.join(sourceDir, 'node_modules', name), dependency, 'dir');
  }
  const entry = VersionFieldSchema.parse(LooseRecordSchema.parse(manifest['bin'])['cz']);
  return {
    run: async (...args) => {
      await promisify(execFile)(process.execPath, [path.join(packageDir, entry), ...args], { cwd: tempDir.path });
    },
  } satisfies CliRunner;
};

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

export const loadPublishedPackages = (): PublishedPackage[] => {
  const releaseManifest = parseToml(
    readFileSync(path.join(workspaceRoot, 'release-targets.toml'), 'utf8'),
    ManifestSchema,
  );
  const packages: PublishedPackage[] = [];

  for (const target of releaseManifest.target) {
    if (target.kind !== 'npm') continue;
    const packageDir = path.join(workspaceRoot, path.dirname(target.version.file));
    const packOutput = execFileSync('pnpm', ['pack', '--dry-run', '--json'], { cwd: packageDir, encoding: 'utf8' });
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
    packages.push({ files, label: target.label, targets });
  }
  return packages;
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
