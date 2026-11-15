import { execFileSync } from 'node:child_process';
import { unlink } from 'node:fs/promises';
import path from 'node:path';

import { workspaceTest } from '#workspace-test';

import type { UpgradeWorkspace } from './upgrade-workspace.ts';

import { createUpgradeWorkspace } from './upgrade-workspace.ts';
export const test = workspaceTest.extend<{
  markdownRepo: {
    init: () => Promise<void>;
    remove: (relativePath: string) => Promise<void>;
    track: (relativePath: string) => void;
  };
  upgradeWorkspace: UpgradeWorkspace;
}>({
  markdownRepo: async ({ initRepo, shell, tempDir }, use) => {
    await use({
      init: async () => {
        await initRepo('.', ['logs/', '.claude/worktrees/']);
        shell.on(
          'git ls-files --cached --others --exclude-standard -z -- *.md :!:**/logs/** :!:**/node_modules/**',
          () =>
            execFileSync(
              'git',
              [
                'ls-files',
                '--cached',
                '--others',
                '--exclude-standard',
                '-z',
                '--',
                '*.md',
                ':!:**/logs/**',
                ':!:**/node_modules/**',
              ],
              { cwd: tempDir.path, encoding: 'utf8' },
            ),
        );
      },
      remove: async relativePath => unlink(path.join(tempDir.path, relativePath)),
      track: relativePath => {
        execFileSync('git', ['add', relativePath], { cwd: tempDir.path, stdio: 'ignore' });
      },
    });
  },
  upgradeWorkspace: async ({ network, tempDir }, use) => {
    await use(createUpgradeWorkspace(network, tempDir));
  },
});
export { describe, expect } from 'vitest';
