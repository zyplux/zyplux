import { describe, expect, test } from '#fixtures';

const workerLimit = 3;

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const settle = () => Promise.resolve();

describe('mapWithConcurrency', () => {
  describe('2.1 mapping items concurrently while preserving output order', () => {
    test('2.1.1 maps each item to its result in original order even when tasks settle out of order', async ({ mapWithConcurrency }) => {
      const inputs = ['a', 'bb', 'ccc', 'dddd', 'eeeee'];

      const labelled = await mapWithConcurrency(inputs, workerLimit, async (text, index) => {
        await delay(inputs.length - index);
        return `${index}:${text}`;
      });

      expect(labelled).toEqual(inputs.map((text, index) => `${index}:${text}`));
    });

    test('2.1.2 never runs more tasks concurrently than the configured limit', async ({ mapWithConcurrency }) => {
      const inputs = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
      let active = 0;
      let peak = 0;

      await mapWithConcurrency(inputs, workerLimit, async () => {
        active += 1;
        peak = Math.max(peak, active);
        await delay(workerLimit);
        active -= 1;
      });

      expect(peak).toBe(workerLimit);
    });

    test('2.1.3 returns an empty array immediately for empty input', async ({ mapWithConcurrency }) => {
      expect(await mapWithConcurrency([], workerLimit, settle)).toEqual([]);
    });
  });

  describe('2.2 validating the concurrency limit argument', () => {
    test('2.2.1 rejects a limit that is not a positive integer', async ({ mapWithConcurrency }) => {
      const fractionalLimit = 2.5;
      const invalidLimits = [NaN, 0, -1, fractionalLimit];

      for (const limit of invalidLimits) {
        await expect(mapWithConcurrency(['a', 'b'], limit, settle)).rejects.toThrow(RangeError);
      }
    });
  });

  describe('2.3 propagating task failures', () => {
    test('2.3.1 rejects with the task error when any task fails', async ({ mapWithConcurrency }) => {
      const mapping = mapWithConcurrency(['a', 'b', 'c'], workerLimit, item =>
        item === 'b' ? Promise.reject(new Error('task failed on b')) : Promise.resolve(item),
      );

      await expect(mapping).rejects.toThrow('task failed on b');
    });
  });
});
