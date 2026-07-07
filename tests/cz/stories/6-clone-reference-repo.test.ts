import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

import { test as base, describe, expect, vi } from '#fixtures';

const test = base.extend<{ tempCwd: undefined }>({
  tempCwd: [
    async ({ tempDir }, use) => {
      const entryCwd = process.cwd();
      process.chdir(tempDir.path);
      try {
        await use(undefined);
      } finally {
        process.chdir(entryCwd);
      }
    },
    { auto: true },
  ],
});

describe('6.1 building the clone url and destination', () => {
  test('6.1.1 builds a github url and destination from an owner/name shorthand', async ({ cz, shell }) => {
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'zyplux/util');

    expect(shell.calls).toContainEqual({
      argv: ['clone', '--depth', '1', '--single-branch', 'https://github.com/zyplux/util.git', 'reference_clones/util'],
      program: 'git',
    });
  });

  test('6.1.2 uses a full url as-is and derives the destination from it', async ({ cz, shell }) => {
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'https://github.com/zyplux/util.git');

    expect(shell.calls).toContainEqual({
      argv: ['clone', '--depth', '1', '--single-branch', 'https://github.com/zyplux/util.git', 'reference_clones/util'],
      program: 'git',
    });
  });

  test('6.1.3 derives the destination from a git@ ssh url, stripping the .git suffix', async ({ cz, shell }) => {
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'git@github.com:zyplux/util.git');

    expect(shell.calls).toContainEqual({
      argv: ['clone', '--depth', '1', '--single-branch', 'git@github.com:zyplux/util.git', 'reference_clones/util'],
      program: 'git',
    });
  });

  test('6.1.4 passes a given ref as the branch flag', async ({ cz, shell }) => {
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'zyplux/util', 'v2.0.0');

    expect(shell.calls).toContainEqual({
      argv: ['clone', '--depth', '1', '--single-branch', '--branch', 'v2.0.0', 'https://github.com/zyplux/util.git', 'reference_clones/util'],
      program: 'git',
    });
  });
});

describe('6.2 re-cloning over an existing destination', () => {
  const dest = path.join('reference_clones', 'existing-scratch-repo');

  test('6.2.1 prompts for confirmation and removes the existing destination before cloning', async ({ cz, shell }) => {
    await mkdir(dest, { recursive: true });
    let promptedWith: string | undefined;
    vi.stubGlobal('prompt', (message?: string) => {
      promptedWith = message;
      return '';
    });
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'existing-scratch-repo');

    expect(promptedWith).toBe(`${dest} exists — rm -rf and re-clone? [enter to continue, ^C to abort]`);
    expect(existsSync(dest)).toBe(false);
    expect(shell.calls).toContainEqual({
      argv: ['clone', '--depth', '1', '--single-branch', 'https://github.com/existing-scratch-repo.git', dest],
      program: 'git',
    });
  });
});
