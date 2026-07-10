import { describe, expect, test } from '#fixtures';

const intervalMs = 1;
const RESOLVES_ON_THIRD_ATTEMPT = 3;

describe('5.1 polling a probe until it returns a defined value', () => {
  test('5.1.1 returns the first defined result without retrying', async ({ poll }) => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return Promise.resolve('found');
    };

    const result = await poll(probe, { attempts: 5, intervalMs });

    expect({ calls, result }).toEqual({ calls: 1, result: 'found' });
  });

  test('5.1.2 retries after undefined results until the probe returns a value', async ({ poll }) => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return Promise.resolve(calls < RESOLVES_ON_THIRD_ATTEMPT ? undefined : 'found');
    };

    const result = await poll(probe, { attempts: 5, intervalMs });

    expect({ calls, result }).toEqual({ calls: RESOLVES_ON_THIRD_ATTEMPT, result: 'found' });
  });

  test('5.1.3 returns undefined once every attempt is exhausted', async ({ poll }) => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return Promise.resolve(undefined);
    };

    const result = await poll<string>(probe, { attempts: 4, intervalMs });

    expect({ calls, result }).toEqual({ calls: 4, result: undefined });
  });

  test('5.1.4 waits intervalMs between attempts', async ({ poll }) => {
    const timestamps: number[] = [];
    const probe = () => {
      timestamps.push(performance.now());
      return Promise.resolve(timestamps.length < RESOLVES_ON_THIRD_ATTEMPT ? undefined : 'found');
    };
    const waitMs = 20;

    await poll(probe, { attempts: 5, intervalMs: waitMs });

    const gaps = timestamps.slice(1).map((time, index) => {
      const previous = timestamps[index];
      if (previous === undefined) throw new Error('unexpected missing timestamp');
      return time - previous;
    });
    expect(gaps.every(gap => gap >= waitMs - 1)).toBe(true);
  });
});
