import type { TempDir } from '@zyplux/spectra/temp-directory';

import { PackageJsonSchema } from '@zyplux/util/contracts';
import { parseJson } from '@zyplux/util/json';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdir, symlink } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const utilDir = fileURLToPath(new URL('../../../../packages/util-ts', import.meta.url));

export const verifyUtilPackage = async (tempDir: TempDir) => {
  const archive = path.join(tempDir.path, 'util.tgz');
  execFileSync('pnpm', ['pack', '--out', archive], { cwd: utilDir, stdio: 'pipe' });
  const consumer = path.join(tempDir.path, 'consumer');
  const packageDir = path.join(consumer, 'node_modules/@zyplux/util');
  await mkdir(packageDir, { recursive: true });
  execFileSync('tar', ['-xzf', archive, '--strip-components=1', '-C', packageDir]);
  const {
    dependencies = {},
    peerDependencies = {},
    peerDependenciesMeta = {},
  } = parseJson(readFileSync(path.join(utilDir, 'package.json'), 'utf8'), PackageJsonSchema);
  const requiredDependencies = new Set([
    ...Object.keys(dependencies),
    ...Object.keys(peerDependencies).filter(name => peerDependenciesMeta[name]?.optional !== true),
  ]);
  for (const name of requiredDependencies) {
    const destination = path.join(consumer, 'node_modules', name);
    await mkdir(path.dirname(destination), { recursive: true });
    await symlink(path.join(utilDir, 'node_modules', name), destination, 'dir');
  }
  await tempDir.write('consumer/package.json', '{"type":"module"}');
  const script = `import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import '@zyplux/util/json';
assert.throws(() => createRequire(import.meta.url).resolve('typescript'), { code: 'MODULE_NOT_FOUND' });`;
  execFileSync(process.execPath, ['--input-type=module', '--eval', script], { cwd: consumer, stdio: 'pipe' });
  await symlink(path.join(utilDir, 'node_modules/typescript'), path.join(consumer, 'node_modules/typescript'), 'dir');
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
