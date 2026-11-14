import { describe, expect, test } from './polling.ts';

describe('3.1 waiting for conditions', () => {
  test('3.1.1 polling settles after a matching observation without a grace period', async ({ pollUntil }) => {
    const observations = [false, true];
    const outcome = await pollUntil(() => observations.shift() ?? false, { timeout: 1000 });
    expect(outcome).toEqual({ error: undefined, settled: true });
    expect(observations).toEqual([]);
  });

  test('3.1.2 polling aborts a read that does not finish before the deadline', async ({ pollUntil }) => {
    let readSignal: AbortSignal | undefined;
    const outcome = await pollUntil(
      signal => {
        readSignal = signal;
        return Promise.withResolvers<boolean>().promise;
      },
      { timeout: 20 },
    );
    expect(outcome.settled).toBe(false);
    expect(readSignal?.aborted).toBe(true);
    expect(outcome.error).toBeInstanceOf(Error);
  });

  test('3.1.3 a matching observation must survive the grace period', async ({ pollUntil }) => {
    const observations = [true, false, true, true];
    const outcome = await pollUntil(() => observations.shift() ?? false, { grace: 10, interval: 1, timeout: 1000 });
    expect(outcome.settled).toBe(true);
    expect(observations).toEqual([]);
  });

  test('3.1.4 the deadline also bounds the grace period', async ({ pollUntil }) => {
    const outcome = await pollUntil(() => true, { grace: 1000, timeout: 20 });
    expect(outcome.settled).toBe(false);
  });
});
