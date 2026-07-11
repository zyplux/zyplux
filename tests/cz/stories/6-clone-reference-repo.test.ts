import { describe, expect, tempCwdTest as test } from '#fixtures';

type CloneCase = [shape: string, args: string[], expectedArgv: string[]];

const cloneCases: CloneCase[] = [
  [
    'builds a github url and destination from an owner/name shorthand',
    ['zyplux/util'],
    ['clone', '--depth', '1', '--single-branch', 'https://github.com/zyplux/util.git', 'reference_clones/util'],
  ],
  [
    'uses a full url as-is and derives the destination from it',
    ['https://github.com/zyplux/util.git'],
    ['clone', '--depth', '1', '--single-branch', 'https://github.com/zyplux/util.git', 'reference_clones/util'],
  ],
  [
    'derives the destination from a git@ ssh url, stripping the .git suffix',
    ['git@github.com:zyplux/util.git'],
    ['clone', '--depth', '1', '--single-branch', 'git@github.com:zyplux/util.git', 'reference_clones/util'],
  ],
  [
    'passes a given ref as the branch flag',
    ['zyplux/util', 'v2.0.0'],
    [
      'clone',
      '--depth',
      '1',
      '--single-branch',
      '--branch',
      'v2.0.0',
      'https://github.com/zyplux/util.git',
      'reference_clones/util',
    ],
  ],
];

describe('6.1 building the clone url and destination', () => {
  test.for(cloneCases)('%s', async ([, args, expectedArgv], { cz, shell }) => {
    shell.on('git clone', '');

    await cz.run('clone-reference-repo', ...args);

    expect(shell.calls).toContainEqual({ argv: expectedArgv, program: 'git' });
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
