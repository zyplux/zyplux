import { libraryTest } from '@zyplux/spectra';
import { LapTimer } from '@zyplux/util/lap-timer';
import { setImmediate } from 'node:timers/promises';
import { format } from 'node:util';
import { vi } from 'vitest';

export const test = libraryTest
  .extend('format', () => format)
  .extend('setImmediate', () => setImmediate)
  .extend<{
    clock: { now: number };
    timer: LapTimer;
  }>({
    clock: [
      async ({}, use) => {
        const clock = { now: 0 };
        const spy = vi.spyOn(performance, 'now').mockImplementation(() => clock.now);
        try {
          await use(clock);
        } finally {
          spy.mockRestore();
        }
      },
      { auto: true },
    ],
    timer: async ({}, use) => {
      await use(new LapTimer());
    },
  });
export { expect } from 'vitest';
