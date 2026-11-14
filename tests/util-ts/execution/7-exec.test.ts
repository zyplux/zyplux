import { describe, expect, test } from './execution.ts';

const node = process.execPath;
const FAILING_EXIT_CODE = 3;
const SIGTERM_EXIT_CODE = 143;
const PASSTHROUGH_FAILURES: [story: string, argv: [string, ...string[]], message: string][] = [
  ['3 rejects a nonzero exit', [node, '-e', `process.exit(${FAILING_EXIT_CODE})`], 'exit code 3'],
  ['4 rejects a missing executable', ['zyplux-missing-command-probe'], 'ENOENT'],
  ['5 rejects termination by a signal', [node, '-e', `process.kill(process.pid, 'SIGTERM')`], 'exit code unknown'],
];

describe('7.1 capturing process output', () => {
  test('7.1.1 resolves with stdout, stderr, and the exit code', async ({ run }) => {
    const script = `process.stdout.write('out'); process.stderr.write('err');`;

    const result = await run([node, '-e', script]).quiet();

    expect(result.exitCode).toBe(0);
    expect(result.stdout.toString()).toBe('out');
    expect(result.stderr.toString()).toBe('err');
  });

  test('7.1.2 decodes text with an explicit encoding', async ({ run }) => {
    const text = await run([node, '-e', `process.stdout.write('hi')`]).quiet().text('hex');

    expect(text).toBe(Buffer.from('hi').toString('hex'));
  });
});

describe('7.2 configuring the spawn through chained calls', () => {
  test('7.2.1 runs in a chained working directory', async ({ run, tempDir }) => {
    const cwdSeenByChild = await run([node, '-e', `process.stdout.write(process.cwd())`])
      .cwd(tempDir.path)
      .quiet()
      .text();

    expect(cwdSeenByChild).toBe(tempDir.path);
  });

  test('7.2.2 overlays chained environment variables onto the parent environment', async ({ run }) => {
    const script = `process.stdout.write(process.env.STORY_PROBE + ':' + typeof process.env.PATH)`;

    const probe = await run([node, '-e', script]).env({ STORY_PROBE: '42' }).quiet().text();

    expect(probe).toBe('42:string');
  });
});

describe('7.3 feeding stdin and merging streams', () => {
  test('7.3.1 pipes a provided stdin into the process', async ({ run }) => {
    const echoed = await run([node, '-e', `process.stdin.pipe(process.stdout)`], { stdin: 'ping' }).quiet().text();

    expect(echoed).toBe('ping');
  });

  test('7.3.2 interleaves stdout and stderr when merge is requested', async ({ run }) => {
    const script = `process.stdout.write('a'); process.stderr.write('b');`;

    const result = await run([node, '-e', script], { merge: true }).quiet();

    expect(result.stdout.toString()).toMatch(/^(ab|ba)$/);
    expect(result.stderr.length).toBe(0);
  });
});

describe('7.4 failing commands', () => {
  test('7.4.1 rejects with an ExecError carrying the exit code', async ({ run }) => {
    const script = `process.stderr.write('boom'); process.exit(${FAILING_EXIT_CODE})`;

    const failing = run([node, '-e', script]).quiet();

    await expect(failing).rejects.toMatchObject({ exitCode: FAILING_EXIT_CODE, name: 'ExecError' });
  });

  test('7.4.2 resolves a failing command when nothrow is chained', async ({ run }) => {
    const result = await run([node, '-e', `process.exit(${FAILING_EXIT_CODE})`])
      .nothrow()
      .quiet();

    expect(result.exitCode).toBe(FAILING_EXIT_CODE);
  });

  test('7.4.3 rejects when argv is empty', async ({ run }) => {
    await expect(run([]).quiet()).rejects.toThrow('argv must contain at least a command');
  });

  test('7.4.4 rejects when the command does not exist', async ({ run }) => {
    await expect(run(['zyplux-missing-command-probe']).quiet()).rejects.toThrow();
  });

  test('7.4.5 rejects a command terminated by a signal', async ({ run }) => {
    const stopped = run([node, '-e', `process.kill(process.pid, 'SIGTERM')`]).quiet();

    await expect(stopped).rejects.toMatchObject({ exitCode: SIGTERM_EXIT_CODE, name: 'ExecError' });
  });

  test('7.4.6 reports signal termination as failure when nothrow is chained', async ({ run }) => {
    const stopped = await run([node, '-e', `process.kill(process.pid, 'SIGTERM')`]).nothrow().quiet();

    expect(stopped.exitCode).toBe(SIGTERM_EXIT_CODE);
  });
});

describe('7.5 sharing the parent terminal', () => {
  test('7.5.1 passes input and both output streams through the parent', async ({ runWithParent }) => {
    const script = `process.stdin.pipe(process.stdout); process.stderr.write('error stream');`;

    const { stderr, stdout } = await runWithParent(script, 'terminal input');

    expect([stdout.toString(), stderr.toString()]).toEqual(['terminal input', 'error stream']);
  });

  test('7.5.2 runs in the requested working directory', async ({ runPassthrough, tempDir }) => {
    await runPassthrough([node, '-e', `require('node:fs').writeFileSync('terminal-marker', '')`], tempDir.path);

    expect(tempDir.exists('terminal-marker')).toBe(true);
  });

  test.for(PASSTHROUGH_FAILURES)('7.5.%s', async ([, argv, message], { runPassthrough }) => {
    await expect(runPassthrough(argv)).rejects.toThrow(message);
  });
});
