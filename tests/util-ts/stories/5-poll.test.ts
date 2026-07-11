import { describe, expect, test } from '#fixtures';

const intervalMs = 1;
const RESOLVES_ON_THIRD_ATTEMPT = 3;
const ATTEMPTS_WITH_ROOM_TO_SPARE = 5;
const ATTEMPTS_UNTIL_EXHAUSTED = 4;

type PollCase = [
  shape: string,
  attempts: number,
  resolveAtCall: number,
  expectedCalls: number,
  expectedResult: string | undefined,
];

const pollCases: PollCase[] = [
  ['returns the first defined result without retrying', ATTEMPTS_WITH_ROOM_TO_SPARE, 1, 1, 'found'],
  [
    'retries after undefined results until the probe returns a value',
    ATTEMPTS_WITH_ROOM_TO_SPARE,
    RESOLVES_ON_THIRD_ATTEMPT,
    RESOLVES_ON_THIRD_ATTEMPT,
    'found',
  ],
  [
    'returns undefined once every attempt is exhausted',
    ATTEMPTS_UNTIL_EXHAUSTED,
    Infinity,
    ATTEMPTS_UNTIL_EXHAUSTED,
    undefined,
  ],
];

describe('5.1 polling a probe until it returns a defined value', () => {
  test.for(pollCases)('%s', async ([, attempts, resolveAtCall, expectedCalls, expectedResult], { poll }) => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return Promise.resolve(calls >= resolveAtCall ? 'found' : undefined);
    };

    const result = await poll<string>(probe, { attempts, intervalMs });

    expect({ calls, result }).toEqual({ calls: expectedCalls, result: expectedResult });
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
