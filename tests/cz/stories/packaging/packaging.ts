import { libraryTest } from '@zyplux/spectra/library-test-api';

import type { TsconfigPresets } from './package-consumer.ts';

import { loadTsconfigPresets, verifyPublishedPackages, verifyUtilPackage } from './package-consumer.ts';
export const test = libraryTest.extend<{
  tsconfigPresets: TsconfigPresets;
  verifyPublishedPackages: () => void;
  verifyUtilPackage: () => Promise<void>;
}>({
  tsconfigPresets: async ({}, use) => {
    await use(loadTsconfigPresets());
  },
  verifyPublishedPackages: async ({ tempDir }, use) => {
    await use(() => {
      verifyPublishedPackages(tempDir);
    });
  },
  verifyUtilPackage: async ({ tempDir }, use) => {
    await use(() => verifyUtilPackage(tempDir));
  },
});
export { describe, expect } from 'vitest';
