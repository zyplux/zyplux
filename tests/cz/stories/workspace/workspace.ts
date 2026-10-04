import { workspaceTest } from '#workspace-test';

import type { UpgradeWorkspace } from './upgrade-workspace.ts';

import { createUpgradeWorkspace } from './upgrade-workspace.ts';
export const test = workspaceTest.extend<{ upgradeWorkspace: UpgradeWorkspace }>({
  upgradeWorkspace: async ({ network, tempDir }, use) => {
    await use(createUpgradeWorkspace(network, tempDir));
  },
});
export { describe, expect } from 'vitest';
