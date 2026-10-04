import { describe, expect, test } from './reporting.ts';

describe('4.1 recording test runs', () => {
  test('4.1.1 a shared test run records each project and closes its journal streams', ({ journalRun }) => {
    expect(journalRun).toMatchInlineSnapshot(`
      {
        "alpha": "<6>run start <timestamp>
      <3>FAIL <root>/alpha.test.ts > failing
      <3>  primary failure
      <3>  Error: stack donor
      <3>FAIL — 3 tests: 1 passed, 1 failed, 1 pending
      ",
        "alphaConsole": "<6><root>/alpha.test.ts module output
      <6><root>/alpha.test.ts > passing alpha output
      ",
        "beta": "<6>run start <timestamp>
      <6>pass — 1 tests: 1 passed, 0 failed, 0 pending
      ",
        "betaConsole": "<4><root>/beta.test.ts > passing beta output
      ",
        "exitCode": 1,
        "gamma": "<6>run start <timestamp>
      <3>FAIL <root>/gamma.test.ts > broken suite
      <3>  Error: setup failure
      <3>FAIL — 1 tests: 0 passed, 0 failed, 1 pending
      ",
        "unnamed": "<6>run start <timestamp>
      <6>pass — 1 tests: 1 passed, 0 failed, 0 pending
      ",
        "unnamedConsole": "<6><root>/unnamed.test.ts > passing unnamed output
      ",
      }
    `);
  });
});

describe('4.2 handling an unavailable journal', () => {
  test('4.2.1 an unavailable journal leaves the test runner usable', async ({ createJournaldReporter, errorSpy }) => {
    const reporter = createJournaldReporter({ socketPath: '/missing-spectra-journal' });
    reporter.onTestRunStart();
    reporter.onUserConsoleLog({ content: 'unattributed output', size: 1, taskId: 'missing', time: 0, type: 'stdout' });
    await reporter.onTestRunEnd([], [{ message: 'test failure', name: 'Error' }], 'failed');
    expect(errorSpy).not.toHaveBeenCalled();
  });

  test('4.2.2 a journal connection failure is reported without changing the test outcome', async ({
    createJournaldReporter,
    errorSpy,
  }) => {
    const reporter = createJournaldReporter({ isEnabled: true, socketPath: '/missing-spectra-journal' });
    reporter.onTestRunStart();
    reporter.onUserConsoleLog({ content: '', size: 1, time: 0, type: 'stdout' });
    reporter.onUserConsoleLog({
      content: 'unattributed output\nmore output',
      size: 1,
      taskId: 'missing',
      time: 0,
      type: 'stderr',
    });
    await reporter.onTestRunEnd([], [{ message: 'test failure', name: 'Error' }], 'failed');
    expect(errorSpy.mock.calls).toEqual([
      ['recording spectra-console to the journal failed', expect.any(Error)],
      ['recording spectra to the journal failed', expect.any(Error)],
    ]);
  });
});
