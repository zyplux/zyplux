import { libraryTest } from '@zyplux/spectra';
import { poll } from '@zyplux/util';
import { setTimeout as sleep } from 'node:timers/promises';
import { vi } from 'vitest';

export const test = libraryTest
  .extend('poll', () => poll)
  .extend<{ sleep: typeof sleep }>({
    sleep: async ({}, use) => {
      vi.mocked(sleep).mockResolvedValue(undefined);
      try {
        await use(sleep);
      } finally {
        vi.mocked(sleep).mockReset();
      }
    },
  });

export { describe, expect } from 'vitest';
