import { mapWithConcurrency } from '@zyplux/util';
import { describe, expect, it } from 'vitest';

const workerLimit = 3;

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const settle = () => Promise.resolve();

describe('mapWithConcurrency', () => {
  it('maps in input order and passes each item its index even as tasks finish out of order', async () => {
    const inputs = ['a', 'bb', 'ccc', 'dddd', 'eeeee'];
    const labelled = await mapWithConcurrency(inputs, workerLimit, async (text, index) => {
      await delay(inputs.length - index);
      return `${index}:${text}`;
    });
    expect(labelled).toEqual(inputs.map((text, index) => `${index}:${text}`));
  });

  it('never runs more tasks at once than the limit', async () => {
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

  it('tolerates empty input', async () => {
    expect(await mapWithConcurrency([], workerLimit, settle)).toEqual([]);
  });
});
