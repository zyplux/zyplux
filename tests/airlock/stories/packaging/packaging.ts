import { ManifestSchema } from '@zyplux/airlock/contracts';
import { libraryTest } from '@zyplux/spectra/library-test-api';
import { parseToml } from '@zyplux/util/toml';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const workspaceRoot = fileURLToPath(new URL('../../../../', import.meta.url));

export const test = libraryTest.extend('verifyPublishedPackages', ({ tempDir }) => () => {
  const manifest = parseToml(readFileSync(path.join(workspaceRoot, 'airlock-targets.toml'), 'utf8'), ManifestSchema);
  for (const target of manifest.target) {
    if (target.kind !== 'npm') continue;
    const dir = path.join(workspaceRoot, path.dirname(target.version.file));
    const archive = path.join(tempDir.path, `${path.basename(dir)}.tgz`);
    execFileSync('pnpm', ['pack', '--out', archive], { cwd: dir, stdio: 'inherit' });
  }
});

export { describe } from 'vitest';
