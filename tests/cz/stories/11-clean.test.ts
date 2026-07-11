// unparametrized
import { describe, expect, tempCwdTest as test } from '#fixtures';

describe('11.1 cleaning a single repo', () => {
  test('11.1.1 removes gitignored build artifacts and caches', async ({ cz, initRepo, tempDir, writeArtifacts }) => {
    await initRepo('.');
    await writeArtifacts('.');

    await cz.run('clean');

    expect(tempDir.exists('node_modules')).toBe(false);
    expect(tempDir.exists('dist')).toBe(false);
  });

  test('11.1.2 protects dotenv files by default even though they are gitignored', async ({
    cz,
    initRepo,
    tempDir,
    writeArtifacts,
  }) => {
    await initRepo('.');
    await writeArtifacts('.');
    await tempDir.write('.env.local', 'SECRET=2');

    await cz.run('clean');

    expect(tempDir.exists('.env')).toBe(true);
    expect(tempDir.exists('.env.local')).toBe(true);
    expect(tempDir.exists('node_modules')).toBe(false);
  });

  test('11.1.3 dry-run reports what would be removed without deleting anything', async ({
    cz,
    initRepo,
    logs,
    tempDir,
    writeArtifacts,
  }) => {
    await initRepo('.');
    await writeArtifacts('.');

    await cz.run('clean', '--dry-run');

    expect(tempDir.exists('node_modules')).toBe(true);
    expect(logs).toHaveLogged('  Would remove node_modules/');
  });

  test('11.1.4 reports nothing to clean when no gitignored artifacts exist', async ({ cz, initRepo, logs }) => {
    await initRepo('.');

    await cz.run('clean');

    expect(logs).toHaveLogged('.: nothing to clean');
  });
});

describe('11.2 discovering every repo under a non-repo directory', () => {
  test('11.2.1 cleans every nested git repo found under the current directory', async ({
    cz,
    initRepo,
    tempDir,
    writeArtifacts,
  }) => {
    await initRepo('repo-a');
    await writeArtifacts('repo-a');
    await initRepo('repo-b');
    await writeArtifacts('repo-b');

    await cz.run('clean');

    expect(tempDir.exists('repo-a/node_modules')).toBe(false);
    expect(tempDir.exists('repo-b/node_modules')).toBe(false);
  });

  test('11.2.2 discovers repos in dot-prefixed directories too', async ({ cz, initRepo, tempDir, writeArtifacts }) => {
    await initRepo('.github');
    await writeArtifacts('.github');

    await cz.run('clean');

    expect(tempDir.exists('.github/node_modules')).toBe(false);
  });
});

describe('11.3 excluding paths', () => {
  test('11.3.1 skips a whole repo named by --exclude', async ({ cz, initRepo, logs, tempDir, writeArtifacts }) => {
    await initRepo('repo-a');
    await writeArtifacts('repo-a');
    await initRepo('repo-b');
    await writeArtifacts('repo-b');

    await cz.run('clean', '--exclude', 'repo-b');

    expect(tempDir.exists('repo-a/node_modules')).toBe(false);
    expect(tempDir.exists('repo-b/node_modules')).toBe(true);
    expect(logs).toHaveLogged('repo-b: skipped (--exclude)');
  });

  test('11.3.2 protects a subfolder named by --exclude within a cleaned repo', async ({
    cz,
    initRepo,
    tempDir,
    writeArtifacts,
  }) => {
    await initRepo('.', ['vendor-cache/']);
    await writeArtifacts('.');
    await tempDir.write('vendor-cache/keep.txt', 'keep');

    await cz.run('clean', '--exclude', 'vendor-cache');

    expect(tempDir.exists('vendor-cache')).toBe(true);
    expect(tempDir.exists('node_modules')).toBe(false);
  });

  test('11.3.3 does not let a skipped repo name protect a same-named ignored subfolder elsewhere', async ({
    cz,
    initRepo,
    tempDir,
    writeArtifacts,
  }) => {
    await initRepo('repo-a', ['repo-b/']);
    await writeArtifacts('repo-a');
    await tempDir.write('repo-a/repo-b/keep.txt', 'keep');
    await initRepo('repo-b');
    await writeArtifacts('repo-b');

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
