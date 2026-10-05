import type { ShellFake } from '@zyplux/spectra/shell-fake';

import { ensure } from '@zyplux/util/assert';
import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';
import path from 'node:path';
import { expect, vi } from 'vitest';

export const expectNpmPackAndPublish = async ({ calls }: ShellFake, dir: string) => {
  const archive = calls.find(call => call.program === 'pnpm' && call.argv[0] === 'pack')?.argv.at(-1);
  ensure(archive !== undefined, 'npm publication must pack an archive');
  expect(calls).toContainEqual({ argv: ['pack', '--out', archive], cwd: dir, program: 'pnpm' });
  expect(vi.mocked(spawn)).toHaveBeenCalledWith('npm', ['publish', archive, '--access', 'public'], {
    cwd: dir,
    stdio: 'inherit',
  });
  await expect(access(path.dirname(archive))).rejects.toMatchObject({ code: 'ENOENT' });
};
