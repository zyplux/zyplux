import { execFileSync } from 'node:child_process';
import path from 'node:path';

import type { TempDir } from '#fixtures';

import { describe, expect, tempCwdTest as test } from '#fixtures';

const runGit = (cwd: string, ...args: string[]) => {
  execFileSync('git', args, { cwd, stdio: 'ignore' });
};

const initRepo = async (tempDir: TempDir, relativeDir: string, extraIgnored: string[] = []) => {
  const ignored = ['node_modules/', 'dist/', '.env', '.env.*', ...extraIgnored];
  await tempDir.write(path.join(relativeDir, '.gitignore'), `${ignored.join('\n')}\n`);
  const repoPath = path.join(tempDir.path, relativeDir);
  runGit(repoPath, 'init', '-q');
  runGit(repoPath, 'add', '.gitignore');
  runGit(repoPath, '-c', 'user.email=test@example.com', '-c', 'user.name=Test', 'commit', '-qm', 'init');
};

const writeArtifacts = async (tempDir: TempDir, relativeDir: string) => {
  await tempDir.write(path.join(relativeDir, 'node_modules/pkg/index.js'), 'x');
  await tempDir.write(path.join(relativeDir, 'dist/out.js'), 'x');
  await tempDir.write(path.join(relativeDir, '.env'), 'SECRET=1');
};

describe('11.1 cleaning a single repo', () => {
  test('11.1.1 removes gitignored build artifacts and caches', async ({ cz, tempDir }) => {
    await initRepo(tempDir, '.');
    await writeArtifacts(tempDir, '.');

    await cz.run('clean');

    expect(tempDir.exists('node_modules')).toBe(false);
    expect(tempDir.exists('dist')).toBe(false);
  });

  test('11.1.2 protects dotenv files by default even though they are gitignored', async ({ cz, tempDir }) => {
    await initRepo(tempDir, '.');
    await writeArtifacts(tempDir, '.');
    await tempDir.write('.env.local', 'SECRET=2');

    await cz.run('clean');

    expect(tempDir.exists('.env')).toBe(true);
    expect(tempDir.exists('.env.local')).toBe(true);
    expect(tempDir.exists('node_modules')).toBe(false);
  });

  test('11.1.3 dry-run reports what would be removed without deleting anything', async ({ cz, logs, tempDir }) => {
    await initRepo(tempDir, '.');
    await writeArtifacts(tempDir, '.');

    await cz.run('clean', '--dry-run');

    expect(tempDir.exists('node_modules')).toBe(true);
    expect(logs.logLines).toContain('  Would remove node_modules/');
  });

  test('11.1.4 reports nothing to clean when no gitignored artifacts exist', async ({ cz, logs, tempDir }) => {
    await initRepo(tempDir, '.');

    await cz.run('clean');

    expect(logs.logLines).toContain('.: nothing to clean');
  });
});

describe('11.2 discovering every repo under a non-repo directory', () => {
  test('11.2.1 cleans every nested git repo found under the current directory', async ({ cz, tempDir }) => {
    await initRepo(tempDir, 'repo-a');
    await writeArtifacts(tempDir, 'repo-a');
    await initRepo(tempDir, 'repo-b');
    await writeArtifacts(tempDir, 'repo-b');

    await cz.run('clean');

    expect(tempDir.exists('repo-a/node_modules')).toBe(false);
    expect(tempDir.exists('repo-b/node_modules')).toBe(false);
  });

  test('11.2.2 discovers repos in dot-prefixed directories too', async ({ cz, tempDir }) => {
    await initRepo(tempDir, '.github');
    await writeArtifacts(tempDir, '.github');

    await cz.run('clean');

    expect(tempDir.exists('.github/node_modules')).toBe(false);
  });
});

describe('11.3 excluding paths', () => {
  test('11.3.1 skips a whole repo named by --exclude', async ({ cz, logs, tempDir }) => {
    await initRepo(tempDir, 'repo-a');
    await writeArtifacts(tempDir, 'repo-a');
    await initRepo(tempDir, 'repo-b');
    await writeArtifacts(tempDir, 'repo-b');

    await cz.run('clean', '--exclude', 'repo-b');

    expect(tempDir.exists('repo-a/node_modules')).toBe(false);
    expect(tempDir.exists('repo-b/node_modules')).toBe(true);
    expect(logs.logLines).toContain('repo-b: skipped (--exclude)');
  });

  test('11.3.2 protects a subfolder named by --exclude within a cleaned repo', async ({ cz, tempDir }) => {
    await initRepo(tempDir, '.', ['vendor-cache/']);
    await writeArtifacts(tempDir, '.');
    await tempDir.write('vendor-cache/keep.txt', 'keep');

    await cz.run('clean', '--exclude', 'vendor-cache');

    expect(tempDir.exists('vendor-cache')).toBe(true);
    expect(tempDir.exists('node_modules')).toBe(false);
  });

  test('11.3.3 does not let a skipped repo name protect a same-named ignored subfolder elsewhere', async ({
    cz,
    tempDir,
  }) => {
    await initRepo(tempDir, 'repo-a', ['repo-b/']);
    await writeArtifacts(tempDir, 'repo-a');
    await tempDir.write('repo-a/repo-b/keep.txt', 'keep');
    await initRepo(tempDir, 'repo-b');
    await writeArtifacts(tempDir, 'repo-b');

    await cz.run('clean', '--exclude', 'repo-b');

    expect(tempDir.exists('repo-a/repo-b')).toBe(false);
    expect(tempDir.exists('repo-b/node_modules')).toBe(true);
  });
});

describe('11.4 error handling', () => {
  test('11.4.1 fails when no git repo is found at or under the current directory', async ({ cz }) => {
    await expect(cz.run('clean')).rejects.toThrow('no git repo found');
  });
});
