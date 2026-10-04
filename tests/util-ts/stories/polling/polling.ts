import { libraryTest } from '@zyplux/spectra/library-test-api';
import { poll } from '@zyplux/util/poll';
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
