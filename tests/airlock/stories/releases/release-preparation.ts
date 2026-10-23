import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { ensure } from '@zyplux/util/assert';
import { execFileSync } from 'node:child_process';
import { symlink } from 'node:fs/promises';
import path from 'node:path';

type PreparationContext = { root: string; shell: ShellFake; tempDir: TempDir };

export const createPreparation = async ({ root, shell, tempDir }: PreparationContext) => {
  await tempDir.write(
    'package.json',
    JSON.stringify({ name: 'release-fixture', packageManager: 'pnpm@12.14.0', private: true }),
  );
  await tempDir.write(
    'packages/util/package.json',
    JSON.stringify({ name: '@zyplux/util', private: true, version: '1.2.3' }),
  );
  await tempDir.write(
    'pnpm-workspace.yaml',
    'packages:\n  - apps/*\n  - packages/*\nversioning:\n  changelog:\n    storage: repository\n',
  );
  await tempDir.write('pyproject.toml', '[tool.uv.workspace]\nmembers = ["apps/cerberus"]\n');
  await tempDir.write(
    'apps/cerberus/pyproject.toml',
    '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\nrequires-python = ">=3.14"\n',
  );
  await tempDir.write(
    '.changeset/feature.md',
    '---\n"@zyplux/util": minor\n"zyplux-cerberus": patch\n---\n\nExpose reviewed target release notes.\n',
  );
  await symlink(path.join(root, 'node_modules'), path.join(tempDir.path, 'node_modules'), 'dir');

  const runCommand = () => {
    const call = shell.calls.at(-1);
    ensure(call !== undefined, 'release preparation must execute a command');
    return execFileSync(call.program, call.argv, { cwd: call.cwd, encoding: 'utf8', stdio: 'pipe' });
  };
  for (const program of ['pnpm', 'uv']) shell.on(program, runCommand);
};
