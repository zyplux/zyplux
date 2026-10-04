import type { ShellFake } from '@zyplux/spectra/fakes/shell-fake';

import { expect } from 'vitest';

export const expectNpmPackAndPublish = ({ calls }: ShellFake, dir: string, tarball: string) => {
  expect(calls).toContainEqual({ argv: ['pack'], cwd: dir, program: 'pnpm' });
  expect(calls).toContainEqual({
    argv: ['publish', tarball, '--access', 'public'],
    cwd: dir,
    program: 'npm',
  });
};
