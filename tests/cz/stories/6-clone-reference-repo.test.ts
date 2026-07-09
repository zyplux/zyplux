import { describe, expect, tempCwdTest as test } from '#fixtures';

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
      argv: [
        'clone',
        '--depth',
        '1',
        '--single-branch',
        '--branch',
        'v2.0.0',
        'https://github.com/zyplux/util.git',
        'reference_clones/util',
      ],
      program: 'git',
    });
  });
});

describe('6.2 re-cloning over an existing destination', () => {
  test('6.2.1 prompts for confirmation and removes the existing destination before cloning', async ({
    cz,
    prompt,
    shell,
    tempDir,
  }) => {
    await tempDir.write('reference_clones/existing-scratch-repo/.keep', '');
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', 'existing-scratch-repo');

    expect(prompt.messages).toEqual([
      'reference_clones/existing-scratch-repo exists — rm -rf and re-clone? [enter to continue, ^C to abort]',
    ]);
    expect(tempDir.exists('reference_clones/existing-scratch-repo')).toBe(false);
    expect(shell.calls).toContainEqual({
      argv: [
        'clone',
        '--depth',
        '1',
        '--single-branch',
        'https://github.com/existing-scratch-repo.git',
        'reference_clones/existing-scratch-repo',
      ],
      program: 'git',
    });
  });
});
