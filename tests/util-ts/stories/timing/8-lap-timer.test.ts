import { expect, test } from './timing.ts';

const API_ACTIVATION_MS = 20.4;
const FAILURE_DURATION_MS = 12;
const LONG_RESULT = 'long';
const LONG_DURATION_MS = 20;
const SHORT_RESULT = 'short';
const SHORT_DURATION_MS = 10;
const STARTUP_DURATION_MS = 10;
const TOTAL_DURATION_MS = 30;
const WORKER_ACTIVATION_MS = 25.6;

test('8.1.1 laps can contain independently measured concurrent work', async ({ clock, timer }) => {
  let finishLong!: (result: string) => void;
  let finishShort!: (result: string) => void;

  const preparation = timer.lap('preparation', [
    ['long operation', () => new Promise<string>(resolve => (finishLong = resolve))],
    ['short operation', () => new Promise<string>(resolve => (finishShort = resolve))],
  ]);
  clock.now = SHORT_DURATION_MS;
  finishShort(SHORT_RESULT);
  await Promise.resolve();
  clock.now = LONG_DURATION_MS;
  finishLong(LONG_RESULT);
  expect(await preparation).toEqual([LONG_RESULT, SHORT_RESULT]);
  timer.lapAndStop('startup', () => {
    clock.now = TOTAL_DURATION_MS;
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

test('8.1.2 parallel laps can contain nested operation arrays', async ({ clock, timer }) => {
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
  clock.now = SHORT_DURATION_MS;
  finishConfig('config');
  await Promise.resolve();
  clock.now = FAILURE_DURATION_MS;
  finishWorker('worker');
  await Promise.resolve();
  clock.now = LONG_DURATION_MS;
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

test('8.1.3 a measured operation retains its duration when it fails', async ({ clock, timer }) => {
  const operation = timer.lap('operation', () => {
    clock.now = FAILURE_DURATION_MS;
    return Promise.reject(new Error('failed'));
  });

  await expect(operation).rejects.toThrow('failed');
  expect(timer.timings).toEqual({ operation: FAILURE_DURATION_MS });
});

test('8.1.4 a failed parallel lap waits for its remaining work before returning', async ({ setImmediate, timer }) => {
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

test('8.1.5 parallel laps report every failure, including synchronous ones', async ({ timer }) => {
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

test('8.1.6 function laps can overlap without sharing timing state', async ({ clock, timer }) => {
  let finishBuild!: () => void;

  const builds = timer.lap('builds', [['image', () => new Promise<void>(resolve => (finishBuild = resolve))]]);
  timer.lap('setup', () => {
    clock.now = SHORT_DURATION_MS;
  });
  clock.now = LONG_DURATION_MS;
  finishBuild();
  await builds;
  timer.lapAndStop('remaining', () => {
    clock.now = TOTAL_DURATION_MS;
  });

  expect(timer.timingsWithTotal).toEqual({
    builds: { image: LONG_DURATION_MS, total: LONG_DURATION_MS },
    remaining: SHORT_DURATION_MS,
    setup: SHORT_DURATION_MS,
    total: TOTAL_DURATION_MS,
  });
});

test('8.1.7 stopping a nested marker timer returns its parent', ({ clock, timer }) => {
  clock.now = SHORT_DURATION_MS;
  const operationTimer = timer.lap('operation 1');
  clock.now = FAILURE_DURATION_MS;
  operationTimer.lap('operation 2.1');
  clock.now = LONG_DURATION_MS;

  operationTimer.lapAndStop('operation 2.2').lap('operation 2');

  clock.now = LONG_DURATION_MS + 1;

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

test('8.1.8 console formatting prints every level of nested timings', ({ clock, format, timer }) => {
  timer.lapAndStop('config and build', preparation => {
    preparation.lap('config', config => {
      config.lap('configure', configure => {
        clock.now = SHORT_DURATION_MS;
        configure.lap('port reservation');
      });
    });
  });

  const printed = format('cluster ready (ms)', timer);
  expect(printed).toContain("configure: { 'port reservation': 10, total: 10 }");
  expect(printed).toContain('cluster ready (ms)');
  expect(printed).not.toContain('[Object]');
});

test('8.1.9 imported timings stay grouped without changing elapsed time', ({ clock, format, timer }) => {
  const activationTimes = new Map([
    ['api', API_ACTIVATION_MS],
    ['worker', WORKER_ACTIVATION_MS],
  ]);

  timer.lapAndStop('start', startup => {
    clock.now = SHORT_DURATION_MS;
    startup.importTimings('unit activation', activationTimes);
    clock.now = TOTAL_DURATION_MS;
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

test('8.1.10 timings can be imported directly from entry arrays and iterators', ({ timer }) => {
  const entries = [
    ['api', API_ACTIVATION_MS],
    ['worker', WORKER_ACTIVATION_MS],
  ] as const;
  const imported = { api: 20, worker: 26 };

  timer.importTimings('array', entries);
  timer.importTimings('iterator', entries.values());

  expect(timer.timings).toEqual({ array: imported, iterator: imported });
});
