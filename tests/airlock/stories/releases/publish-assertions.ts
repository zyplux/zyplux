import type { ShellFake } from '@zyplux/spectra/shell-fake';

import { ensure } from '@zyplux/util/assert';
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { access } from 'node:fs/promises';
import path from 'node:path';
import { expect, vi } from 'vitest';

export const createNotesCapture = (shell: ShellFake) => {
  let notes = '';
  return {
    capture: () => {
      shell.on('gh release create', () => {
        const argv = shell.calls.at(-1)?.argv;
        const notesFile = argv?.[argv.indexOf('--notes-file') + 1];
        ensure(notesFile !== undefined, 'release notes file must be supplied');
        notes = readFileSync(notesFile, 'utf8');
        return '';
      });
    },
    read: () => notes,
  };
};

export const expectGithubRelease = async ({ calls }: ShellFake, tag: string, commit: string) => {
  const call = calls.find(call => {
    const [subcommand, action, releaseTag] = call.argv;
    return call.program === 'gh' && subcommand === 'release' && action === 'create' && releaseTag === tag;
  });
  ensure(call !== undefined, `GitHub release ${tag} must be created`);
  const notesFile = call.argv[call.argv.indexOf('--notes-file') + 1];
  ensure(notesFile !== undefined, 'GitHub release notes must be supplied as a file');
  expect(call.argv).toEqual(['release', 'create', tag, '--notes-file', notesFile, '--target', commit, '--title', tag]);
  await expect(access(path.dirname(notesFile))).rejects.toMatchObject({ code: 'ENOENT' });
};

export const expectNpmPublish = ({ calls }: ShellFake, dir: string) => {
  expect(calls).toContainEqual({ argv: ['publish', '--publish-wait-timeout', '600000'], cwd: dir, program: 'pnpm' });
  expect(vi.mocked(spawn)).toHaveBeenCalledWith('pnpm', ['publish', '--publish-wait-timeout', '600000'], {
    cwd: dir,
    stdio: 'inherit',
  });
};
