import type { TempDir } from '@zyplux/spectra';

import { execFileSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';

import { czTest } from './cli-test.ts';

const enterCwd = (dir: string) => {
  const entryCwd = process.cwd();
  process.chdir(dir);
  return () => {
    process.chdir(entryCwd);
  };
};

const runGit = (cwd: string, ...args: string[]) => {
  execFileSync('git', args, { cwd, stdio: 'ignore' });
};

const createInitRepo =
  (tempDir: TempDir) =>
  async (relativeDir: string, extraIgnored: string[] = []) => {
    const ignored = ['node_modules/', 'dist/', '.env', '.env.*', ...extraIgnored];
    await tempDir.write(path.join(relativeDir, '.gitignore'), `${ignored.join('\n')}\n`);
    const repoPath = path.join(tempDir.path, relativeDir);
    runGit(repoPath, 'init', '-q');
    runGit(repoPath, 'add', '.gitignore');
    runGit(repoPath, '-c', 'user.email=test@example.com', '-c', 'user.name=Test', 'commit', '-qm', 'init');
  };

const createWriteArtifacts = (tempDir: TempDir) => async (relativeDir: string) => {
  await tempDir.write(path.join(relativeDir, 'node_modules/pkg/index.js'), 'x');
  await tempDir.write(path.join(relativeDir, 'dist/out.js'), 'x');
  await tempDir.write(path.join(relativeDir, '.env'), 'SECRET=1');
};

export const workspaceTest = czTest.extend<{
  initRepo: ReturnType<typeof createInitRepo>;
  tempCwd: undefined;
  writeArtifacts: ReturnType<typeof createWriteArtifacts>;
}>({
  initRepo: async ({ tempDir }, use) => {
    await use(createInitRepo(tempDir));
  },
  tempCwd: [
    async ({ tempDir }, use) => {
      const restoreCwd = enterCwd(tempDir.path);
      try {
        await use(undefined);
      } finally {
        restoreCwd();
      }
    },
    { auto: true },
  ],
  writeArtifacts: async ({ tempDir }, use) => {
    await use(createWriteArtifacts(tempDir));
  },
});
