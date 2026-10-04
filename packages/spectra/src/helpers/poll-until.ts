import { setTimeout } from 'node:timers/promises';
import { expect } from 'vitest';

type PollCondition = (signal: AbortSignal) => boolean | Promise<boolean>;
type PollOptions = { grace?: number; interval?: number; timeout: number };

export const pollUntil = async (isSettled: PollCondition, { grace, interval, timeout }: PollOptions) => {
  try {
    await expect
      .poll(
        async ({ signal }) => {
          if (!(await isSettled(signal))) return false;
          if (grace === undefined) return true;
          await setTimeout(grace, undefined, { signal });
          return isSettled(signal);
        },
        { ...(interval !== undefined && { interval }), timeout },
      )
      .toBe(true);
    return { error: undefined, settled: true };
  } catch (error) {
    return { error, settled: false };
  }
};
