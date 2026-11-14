import { describe, expect, test } from './polling.ts';

const DEFAULT_ATTEMPTS = 5;
const DEFAULT_INTERVAL_MS = 1000;
const CUSTOM_INTERVAL_MS = 20;

describe('5.1 polling until the expected result arrives', () => {
  test('5.1.1 returns an immediate match without sleeping', async ({ poll, sleep }) => {
    expect(await poll(() => Promise.resolve('ready'), { until: 'ready' })).toBe('ready');
    expect(sleep).not.toHaveBeenCalled();
  });

  test('5.1.2 retries defined results that do not match', async ({ poll, sleep }) => {
    const states = ['pending', 'ready'];
    expect(await poll(() => Promise.resolve(states.shift()), { until: 'ready' })).toBe('ready');
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.3 defaults to five attempts one second apart without a final sleep', async ({ poll, sleep }) => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return Promise.resolve('pending');
    };
    expect(await poll(probe, { until: 'ready' })).toBeUndefined();
    expect(calls).toBe(DEFAULT_ATTEMPTS);
    expect(sleep).toHaveBeenCalledTimes(DEFAULT_ATTEMPTS - 1);
    expect(sleep).toHaveBeenNthCalledWith(DEFAULT_ATTEMPTS - 1, DEFAULT_INTERVAL_MS);
  });

  test('5.1.4 accepts attempt and interval overrides', async ({ poll, sleep }) => {
    expect(
      await poll(() => Promise.resolve('pending'), { attempts: 2, intervalMs: CUSTOM_INTERVAL_MS, until: 'ready' }),
    ).toBeUndefined();
    expect(sleep).toHaveBeenCalledExactlyOnceWith(CUSTOM_INTERVAL_MS);
  });

  test('5.1.5 accepts any defined result when no condition is supplied', async ({ poll, sleep }) => {
    const states = [undefined, 'BLOCKED'];
    expect(await poll(() => Promise.resolve(states.shift()))).toBe('BLOCKED');
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.6 matches falsy expected values', async ({ poll }) => {
    for (const expected of [false, 0, '']) {
      expect(await poll(() => Promise.resolve(expected), { onExpiry: 'value never matched', until: expected })).toBe(
        expected,
      );
    }
  });

  test('5.1.7 propagates probe failures without retrying', async ({ poll, sleep }) => {
    const failure = new Error('probe failed');
    await expect(poll(() => Promise.reject(failure), { onExpiry: 'poll exhausted' })).rejects.toThrow('probe failed');
    expect(sleep).not.toHaveBeenCalled();
  });

  test('5.1.8 retries while the result equals the supplied value', async ({ poll, sleep }) => {
    const states = ['UNKNOWN', 'BLOCKED'];
    expect(await poll(() => Promise.resolve(states.shift()), { while: 'UNKNOWN' })).toBe('BLOCKED');
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.9 exhausts attempts while the result stays equal', async ({ poll, sleep }) => {
    expect(await poll(() => Promise.resolve('UNKNOWN'), { while: 'UNKNOWN' })).toBeUndefined();
    expect(sleep).toHaveBeenCalledTimes(DEFAULT_ATTEMPTS - 1);
  });

  test('5.1.10 can wait until the result is undefined', async ({ poll, sleep }) => {
    const states = ['pending', undefined];
    await expect(
      poll(() => Promise.resolve(states.shift()), { onExpiry: 'result never disappeared', until: undefined }),
    ).resolves.toBeUndefined();
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.11 handles falsy while values and stops on a different undefined result', async ({ poll, sleep }) => {
    const states = [false, undefined];
    expect(
      await poll(() => Promise.resolve(states.shift()), { onExpiry: 'value stayed false', while: false }),
    ).toBeUndefined();
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.12 throws the expiry message on exhaustion without a final sleep', async ({ poll, sleep }) => {
    await expect(
      poll(() => Promise.resolve('pending'), { attempts: 2, onExpiry: 'not ready', until: 'ready' }),
    ).rejects.toThrow('not ready');
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.13 treats an empty expiry message as required polling', async ({ poll }) => {
    await expect(
      poll(() => Promise.resolve('pending'), { attempts: 1, onExpiry: '', while: 'pending' }),
    ).rejects.toMatchObject({ message: '' });
  });

  test('5.1.14 returns the defined result from a required lookup', async ({ poll, sleep }) => {
    const ids = [undefined, '123'];
    const id = await poll(() => Promise.resolve(ids.shift()), { onExpiry: 'run never started' });
    expect(id).toBe('123');
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.15 accepts an until predicate over the resolved probe result', async ({ poll, sleep }) => {
    const pending = { status: 'pending' };
    const completed = { status: 'completed' };
    const jobs = [pending, completed];

    expect(await poll(() => Promise.resolve(jobs.shift()), { until: job => job?.status === 'completed' })).toBe(
      completed,
    );
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.16 accepts a while predicate and returns a falsy result', async ({ poll, sleep }) => {
    let remaining = 2;

    expect(await poll(() => Promise.resolve(--remaining), { while: count => count > 0 })).toBe(0);
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.17 returns a completed failure for the caller to check', async ({ poll, sleep }) => {
    const completed = { conclusion: 'failure', status: 'completed' };
    const runs = [{ conclusion: 'success', status: 'in_progress' }, completed];
    expect(
      await poll(() => Promise.resolve(runs.shift()), {
        onExpiry: 'workflow did not complete',
        until: run => run?.status === 'completed',
      }),
    ).toBe(completed);
    expect(sleep).toHaveBeenCalledExactlyOnceWith(DEFAULT_INTERVAL_MS);
  });

  test('5.1.18 propagates predicate errors without replacing them with the expiry message', async ({ poll, sleep }) => {
    await expect(
      poll(() => Promise.resolve('ready'), {
        onExpiry: 'poll expired',
        until: () => {
          throw new Error('predicate failed');
        },
      }),
    ).rejects.toThrow('predicate failed');
    expect(sleep).not.toHaveBeenCalled();
  });
});
