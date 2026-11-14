import { czTest } from '#cli-test';

import type { Catalog } from './catalog-workspace.ts';

import { createCatalog } from './catalog-workspace.ts';
export const test = czTest.extend<{ catalog: Catalog }>({
  catalog: async ({ cz, logs, network, tempDir }, use) => {
    await use(createCatalog(cz, tempDir, logs, network));
  },
});
export type { Catalog } from './catalog-workspace.ts';
export type { TempDir } from '@zyplux/spectra/temp-directory';
export { describe, expect } from 'vitest';
