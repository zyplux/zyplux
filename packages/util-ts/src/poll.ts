import { setTimeout } from 'node:timers/promises';

const DEFAULT_ATTEMPTS = 5;
const DEFAULT_INTERVAL_MS = 1000;

type LookupOptions<T> = RequiredPollOptions<T> & { until?: never; while?: undefined };

type Poll = {
  <T>(probe: () => Promise<T>, options: UndefinedMatchOptions<T>): Promise<Awaited<T> & undefined>;
  <T>(probe: () => Promise<T>, options: LookupOptions<T>): Promise<Exclude<Awaited<T>, undefined>>;
  <T>(probe: () => Promise<T>, options: RequiredPollOptions<T>): Promise<Awaited<T>>;
  <T>(probe: () => Promise<T>, options?: PollOptions<T>): Promise<Awaited<T> | undefined>;
};
type PollCondition<T> = PollPredicate<T> | T | undefined;
type PollOptions<T> = {
  attempts?: number;
  intervalMs?: number;
  onExpiry?: string;
} & (
  | { until: PollCondition<NoInfer<Awaited<T>>>; while?: never }
  | { until?: never; while?: PollCondition<NoInfer<Awaited<T>>> }
);
type PollPredicate<T> = (observed: T) => boolean;

type RequiredPollOptions<T> = PollOptions<T> & { onExpiry: string };
type UndefinedMatchOptions<T> = Extract<RequiredPollOptions<T>, { until: unknown }> & { until: undefined };

const isConditionMatch = <T>(observed: T, condition: PollCondition<T>) =>
  typeof condition === 'function'
    ? Reflect.apply(condition, undefined, [observed]) === true
    : Object.is(observed, condition);

export const poll: Poll = async <T>(
  probe: () => Promise<T>,
  { attempts = DEFAULT_ATTEMPTS, intervalMs = DEFAULT_INTERVAL_MS, onExpiry, ...condition }: PollOptions<T> = {},
) => {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const observed = await probe();
    const isMatch =
      'until' in condition ? isConditionMatch(observed, condition.until) : !isConditionMatch(observed, condition.while);
    if (isMatch) return observed;
    if (attempt + 1 < attempts) await setTimeout(intervalMs);
  }
  if (onExpiry !== undefined) throw new Error(onExpiry);
  return;
};
