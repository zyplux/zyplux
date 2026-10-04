import { LapTimer } from '@zyplux/util/lap-timer';
import { setImmediate } from 'node:timers/promises';
import { format } from 'node:util';
import { expect, test, vi } from 'vitest';

const API_ACTIVATION_MS = 20.4;
const FAILURE_DURATION_MS = 12;
const LONG_RESULT = 'long';
const LONG_DURATION_MS = 20;
const SHORT_RESULT = 'short';
const SHORT_DURATION_MS = 10;
const STARTUP_DURATION_MS = 10;
const TOTAL_DURATION_MS = 30;
const WORKER_ACTIVATION_MS = 25.6;

test('laps can contain independently measured concurrent work', async () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();
  let finishLong!: (result: string) => void;
  let finishShort!: (result: string) => void;

  const preparation = timer.lap('preparation', [
    ['long operation', () => new Promise<string>(resolve => (finishLong = resolve))],
    ['short operation', () => new Promise<string>(resolve => (finishShort = resolve))],
  ]);
  now = SHORT_DURATION_MS;
  finishShort(SHORT_RESULT);
  await Promise.resolve();
  now = LONG_DURATION_MS;
  finishLong(LONG_RESULT);
  expect(await preparation).toEqual([LONG_RESULT, SHORT_RESULT]);
  timer.lapAndStop('startup', () => {
    now = TOTAL_DURATION_MS;
  });

  expect(timer.timingsWithTotal).toEqual({
    preparation: {
      'long operation': LONG_DURATION_MS,
      'short operation': SHORT_DURATION_MS,
      total: LONG_DURATION_MS,
    },
    startup: STARTUP_DURATION_MS,
    total: TOTAL_DURATION_MS,
  });
});

test('parallel laps can contain nested operation arrays', async () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();
  let finishBuild!: (result: string) => void;
  let finishConfig!: (result: string) => void;
  let finishWorker!: (result: string) => void;

  const preparation = timer.lap('config and build', [
    ['config', () => new Promise<string>(resolve => (finishConfig = resolve))],
    [
      'build',
      [
        ['image', () => new Promise<string>(resolve => (finishBuild = resolve))],
        ['worker', () => new Promise<string>(resolve => (finishWorker = resolve))],
      ],
    ],
  ]);
  now = SHORT_DURATION_MS;
  finishConfig('config');
  await Promise.resolve();
  now = FAILURE_DURATION_MS;
  finishWorker('worker');
  await Promise.resolve();
  now = LONG_DURATION_MS;
  finishBuild('image');

  expect(await preparation).toEqual(['config', ['image', 'worker']]);
  expect(timer.timings).toEqual({
    'config and build': {
      build: { image: LONG_DURATION_MS, total: LONG_DURATION_MS, worker: FAILURE_DURATION_MS },
      config: SHORT_DURATION_MS,
      total: LONG_DURATION_MS,
    },
  });
});

test('a measured operation retains its duration when it fails', async () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();

  const operation = timer.lap('operation', () => {
    now = FAILURE_DURATION_MS;
    return Promise.reject(new Error('failed'));
  });

  await expect(operation).rejects.toThrow('failed');
  expect(timer.timings).toEqual({ operation: FAILURE_DURATION_MS });
});

test('a failed parallel lap waits for its remaining work before returning', async () => {
  const timer = new LapTimer();
  const failure = new Error('build failed');
  const configuration = Promise.withResolvers<undefined>();
  const failures: unknown[] = [];
  const runPreparation = async () => {
    try {
      await timer.lap('preparation', [
        ['build', () => Promise.reject(failure)],
        ['config', () => configuration.promise],
      ]);
    } catch (error) {
      failures.push(error);
    }
  };
  const preparation = runPreparation();

  try {
    await setImmediate();
    expect(failures).toEqual([]);
  } finally {
    configuration.resolve(undefined);
    await preparation;
  }
  expect(failures).toEqual([failure]);
});

test('parallel laps report every failure, including synchronous ones', async () => {
  const timer = new LapTimer();
  const buildFailure = new Error('build failed');
  const configFailure = new Error('config failed');
  await expect(async () =>
    timer.lap('preparation', [
      [
        'build',
        () => {
          throw buildFailure;
        },
      ],
      ['config', () => Promise.reject(configFailure)],
    ]),
  ).rejects.toMatchObject({ errors: [buildFailure, configFailure] });
});

test('function laps can overlap without sharing timing state', async () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();
  let finishBuild!: () => void;

  const builds = timer.lap('builds', [['image', () => new Promise<void>(resolve => (finishBuild = resolve))]]);
  timer.lap('setup', () => {
    now = SHORT_DURATION_MS;
  });
  now = LONG_DURATION_MS;
  finishBuild();
  await builds;
  timer.lapAndStop('remaining', () => {
    now = TOTAL_DURATION_MS;
  });

  expect(timer.timingsWithTotal).toEqual({
    builds: { image: LONG_DURATION_MS, total: LONG_DURATION_MS },
    remaining: SHORT_DURATION_MS,
    setup: SHORT_DURATION_MS,
    total: TOTAL_DURATION_MS,
  });
});

test('stopping a nested marker timer returns its parent', () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();
  now = SHORT_DURATION_MS;
  const operationTimer = timer.lap('operation 1');
  now = FAILURE_DURATION_MS;
  operationTimer.lap('operation 2.1');
  now = LONG_DURATION_MS;

  operationTimer.lapAndStop('operation 2.2').lap('operation 2');

  now = LONG_DURATION_MS + 1;

  timer.lapAndStop('operation 3');

  expect(timer.timingsWithTotal).toEqual({
    'operation 1': SHORT_DURATION_MS,
    'operation 2': {
      'operation 2.1': FAILURE_DURATION_MS - SHORT_DURATION_MS,
      'operation 2.2': LONG_DURATION_MS - FAILURE_DURATION_MS,
      total: LONG_DURATION_MS - SHORT_DURATION_MS,
    },
    'operation 3': 1,
    total: LONG_DURATION_MS + 1,
  });
});

test('console formatting prints every level of nested timings', () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();

  timer.lapAndStop('config and build', preparation => {
    preparation.lap('config', config => {
      config.lap('configure', configure => {
        now = SHORT_DURATION_MS;
        configure.lap('port reservation');
      });
    });
  });

  const printed = format('cluster ready (ms)', timer);
  expect(printed).toContain("configure: { 'port reservation': 10, total: 10 }");
  expect(printed).toContain('cluster ready (ms)');
  expect(printed).not.toContain('[Object]');
});

test('imported timings stay grouped without changing elapsed time', () => {
  let now = 0;
  vi.spyOn(performance, 'now').mockImplementation(() => now);
  const timer = new LapTimer();
  const activationTimes = new Map([
    ['api', API_ACTIVATION_MS],
    ['worker', WORKER_ACTIVATION_MS],
  ]);

  timer.lapAndStop('start', startup => {
    now = SHORT_DURATION_MS;
    startup.importTimings('unit activation', activationTimes);
    now = TOTAL_DURATION_MS;
    startup.lap('ready');
  });
  activationTimes.set('api', 0);

  expect(timer.timingsWithTotal).toEqual({
    start: {
      ready: TOTAL_DURATION_MS,
      total: TOTAL_DURATION_MS,
      'unit activation': { api: 20, worker: 26 },
    },
    total: TOTAL_DURATION_MS,
  });
  expect(format(timer)).toContain("'unit activation': { api: 20, worker: 26 }");
});

test('timings can be imported directly from entry arrays and iterators', () => {
  const entries = [
    ['api', API_ACTIVATION_MS],
    ['worker', WORKER_ACTIVATION_MS],
  ] as const;
  const imported = { api: 20, worker: 26 };
  const timer = new LapTimer();

  timer.importTimings('array', entries);
  timer.importTimings('iterator', entries.values());

  expect(timer.timings).toEqual({ array: imported, iterator: imported });
});
