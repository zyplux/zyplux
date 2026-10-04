import type { InspectOptions } from 'node:util';

import { inspect } from 'node:util';

type LapFunction = (timer: LapTimer) => unknown;
type LapOperation = readonly [name: string, operation: LapFunction | LapOperations];
type LapOperations = readonly LapOperation[];
type LapResult<Operation> = Operation extends LapOperations
  ? LapResults<Operation>
  : Operation extends (timer: LapTimer) => infer Result
    ? Awaited<Result>
    : never;
type LapResults<Operations extends LapOperations> = {
  -readonly [Index in keyof Operations]: Operations[Index] extends readonly [name: string, operation: infer Operation]
    ? LapResult<Operation>
    : never;
};
type Timings = { [name: string]: number | Timings };

class LapTimer {
  get timings(): Timings {
    return Object.fromEntries(
      [...this.#timings].map(([name, timing]) => [
        name,
        timing instanceof LapTimer ? (timing.#timings.size === 0 ? timing.total : timing.timingsWithTotal) : timing,
      ]),
    );
  }
  get timingsWithTotal() {
    return { ...this.timings, total: this.#totalMs };
  }
  get total() {
    return this.#totalMs;
  }
  readonly #parent: LapTimer | undefined;
  #pendingChild: LapTimer | undefined;
  #previous: number | undefined;

  readonly #startedAt: number;

  readonly #timings = new Map<string, LapTimer | number | Timings>();

  #totalMs = 0;

  constructor(parent?: LapTimer) {
    this.#parent = parent;
    this.#previous = performance.now();
    this.#startedAt = this.#previous;
  }

  importTimings(name: string, timings: Iterable<readonly [name: string, duration: number]>) {
    this.#timings.set(name, Object.fromEntries(Array.from(timings, ([lap, duration]) => [lap, Math.round(duration)])));
  }

  [inspect.custom](_depth: number, options: InspectOptions) {
    return inspect(this.timingsWithTotal, { ...options, depth: Infinity });
  }

  lap(name: string): LapTimer;
  lap<const Operations extends LapOperations>(name: string, operations: Operations): Promise<LapResults<Operations>>;
  lap<Result>(name: string, operation: (timer: LapTimer) => Result): Result;
  lap(name: string, operation?: LapFunction | LapOperations): unknown {
    if (operation === undefined) {
      this.#recordMarker(name);
      const timer = new LapTimer(this);
      this.#pendingChild = timer;
      return timer;
    }
    return this.#executeOperation(name, operation);
  }

  lapAndStop(name: string): LapTimer;
  lapAndStop<const Operations extends LapOperations>(
    name: string,
    operations: Operations,
  ): Promise<LapResults<Operations>>;
  lapAndStop<Result>(name: string, operation: (timer: LapTimer) => Result): Result;
  lapAndStop(name: string, operation?: LapFunction | LapOperations): unknown {
    if (operation === undefined) {
      this.#recordMarker(name);
      this.#stop(this.#previous);
      return this.#parent ?? this;
    }

    try {
      return this.#stopAfter(this.#executeOperation(name, operation));
    } catch (error) {
      this.#stop(performance.now());
      throw error;
    }
  }

  #execute(name: string, operation: (timer: LapTimer) => unknown): unknown {
    if (this.#previous === undefined) throw new Error('timer has not started');
    this.#previous = performance.now();
    const timer = new LapTimer(this);
    this.#timings.set(name, timer);
    try {
      const result = operation(timer);
      if (result instanceof Promise) return timer.#settle(result);
      timer.#stop(performance.now());
      return result;
    } catch (error) {
      timer.#stop(performance.now());
      throw error;
    }
  }
  #executeAll(name: string, operations: LapOperations): unknown {
    return this.#execute(name, async timer => {
      const results = await Promise.allSettled(
        operations.map(async ([operationName, operation]) => await timer.#executeOperation(operationName, operation)),
      );
      const failures: unknown[] = [];
      for (const result of results) {
        if (result.status === 'rejected') failures.push(result.reason);
      }
      if (failures.length === 1) throw failures[0];
      if (failures.length > 1) throw new AggregateError(failures, `${name} failed`);
      return results.map(result => (result.status === 'fulfilled' ? result.value : undefined));
    });
  }
  #executeOperation(name: string, operation: LapFunction | LapOperations): unknown {
    return typeof operation === 'function' ? this.#execute(name, operation) : this.#executeAll(name, operation);
  }
  #recordMarker(name: string) {
    if (this.#previous === undefined) throw new Error('timer has not started');
    const now = performance.now();
    const child = this.#pendingChild;
    this.#timings.set(
      name,
      child !== undefined && child.#previous === undefined ? child : Math.round(now - this.#previous),
    );
    this.#pendingChild = undefined;
    this.#previous = now;
  }

  async #settle(result: Promise<unknown>) {
    try {
      return await result;
    } finally {
      this.#stop(performance.now());
    }
  }

  #stop(stoppedAt: number | undefined) {
    if (stoppedAt === undefined || this.#previous === undefined) return;
    this.#totalMs = Math.round(stoppedAt - this.#startedAt);
    this.#previous = undefined;
  }

  #stopAfter(result: unknown) {
    if (result instanceof Promise) return this.#settle(result);
    this.#stop(performance.now());
    return result;
  }
}

export { LapTimer };
