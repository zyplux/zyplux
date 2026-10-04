import type { TempDir } from '@zyplux/spectra';

import { ManifestSchema, VersionFieldSchema } from '@zyplux/cz/contracts';
import { ensure, parseJson, parseToml } from '@zyplux/util';
import { LooseRecordSchema } from '@zyplux/util/contracts';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdir, symlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const workspaceRoot = fileURLToPath(new URL('../../../../', import.meta.url));
const configDir = path.join(workspaceRoot, 'packages/tsconfig');

export type TsconfigPresets = {
  base: EmitPolicy & { composite: boolean };
  baseDeclaresModules: boolean;
  nodePub: EmitPolicy;
  variants: Record<string, { module: string; moduleResolution: string }>;
};
type EmitPolicy = {
  declarationMap: boolean;
  emitDeclarationOnly: boolean;
  outDir: string;
  rewriteRelativeImportExtensions: boolean;
  tsBuildInfoFile: string;
};
const loadRecord = (file: string) => parseJson(readFileSync(file, 'utf8'), LooseRecordSchema);
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

const packReleaseTargets = (tempDir: TempDir, label?: string) => {
  const releaseManifest = parseToml(
    readFileSync(path.join(workspaceRoot, 'release-targets.toml'), 'utf8'),
    ManifestSchema,
  );
  const packages: { archive: string; dir: string; label: string }[] = [];
  for (const target of releaseManifest.target) {
    if (target.kind !== 'npm' || (label !== undefined && target.label !== label)) continue;
    const dir = path.join(workspaceRoot, path.dirname(target.version.file));
    const archive = path.join(tempDir.path, `${path.basename(dir)}.tgz`);
    execFileSync('pnpm', ['pack', '--out', archive], { cwd: dir, stdio: 'pipe' });
    packages.push({ archive, dir, label: target.label });
  }
  return packages;
};

export const verifyPublishedPackages = (tempDir: TempDir) => {
  packReleaseTargets(tempDir);
};

export const verifyUtilPackage = async (tempDir: TempDir) => {
  const [packed] = packReleaseTargets(tempDir, '@zyplux/util');
  ensure(packed !== undefined, 'no packed release target for @zyplux/util');
  const consumer = path.join(tempDir.path, 'consumer');
  const packageDir = path.join(consumer, 'node_modules/@zyplux/util');
  await mkdir(packageDir, { recursive: true });
  execFileSync('tar', ['-xzf', packed.archive, '--strip-components=1', '-C', packageDir]);
  for (const name of ['smol-toml', 'zod']) {
    await symlink(path.join(packed.dir, 'node_modules', name), path.join(consumer, 'node_modules', name), 'dir');
  }
  await tempDir.write('consumer/package.json', '{"type":"module"}');
  const script = `import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import '@zyplux/util';
assert.throws(() => createRequire(import.meta.url).resolve('typescript'), { code: 'MODULE_NOT_FOUND' });`;
  execFileSync(process.execPath, ['--input-type=module', '--eval', script], { cwd: consumer, stdio: 'pipe' });
  await symlink(
    path.join(workspaceRoot, 'node_modules/typescript'),
    path.join(consumer, 'node_modules/typescript'),
    'dir',
  );
  execFileSync(
    process.execPath,
    [
      '--input-type=module',
      '--eval',
      "import '@zyplux/util/module-references'; import '@zyplux/util/type-dependencies';",
    ],
    { cwd: consumer, stdio: 'pipe' },
  );
};
