import { JournaldReporter } from '@zyplux/spectra/reporters/journald-reporter';
import { mkdir, mkdtemp, rm, symlink, writeFile } from 'node:fs/promises';
import { createServer } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as base, vi } from 'vitest';
import { createVitest } from 'vitest/node';

const runReporter = async (root: string, socketPath: string, hasProjects = true) => {
  const previousExitCode = process.exitCode;
  const vitest = await createVitest(
    { config: false, root, watch: false },
    {
      test: {
        reporters: [new JournaldReporter({ identifier: 'example', socketPath })],
        ...(hasProjects
          ? {
              projects: [
                { test: { include: ['alpha.test.ts'], name: 'alpha' } },
                { test: { include: ['beta.test.ts'], name: 'beta' } },
                { test: { include: ['gamma.test.ts'], name: 'gamma' } },
              ],
            }
          : { include: ['unnamed.test.ts'] }),
      },
    },
  );
  try {
    const { testModules, unhandledErrors } = await vitest.start();
    return testModules.every(module => module.ok()) && unhandledErrors.length === 0 ? 0 : 1;
  } finally {
    await vitest.close();
    process.exitCode = previousExitCode;
  }
};

const runJournalScenario = async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'spectra-reporter-'));
  const recordings = new Map<string, string>();
  const socketPath = path.join(root, 'journal.socket');
  const server = createServer(socket => {
    let recording = '';
    socket.on('data', chunk => (recording += String(chunk)));
    socket.on('end', () => {
      const [identifier = '', , priority, prefixes, syslog, kmsg, terminal, ...lines] = recording.split('\n');
      if (priority !== '6' || prefixes !== '1' || syslog !== '0' || kmsg !== '0' || terminal !== '0') {
        throw new Error('invalid journal stream header');
      }
      recordings.set(identifier, (recordings.get(identifier) ?? '') + lines.join('\n'));
    });
  });
  let exitCode: number;
  try {
    await mkdir(path.join(root, 'node_modules'));
    const vitestDir = path.dirname(fileURLToPath(import.meta.resolve('vitest/package.json')));
    await symlink(vitestDir, path.join(root, 'node_modules/vitest'));
    await new Promise<void>(resolve => server.listen(socketPath, resolve));
    await writeFile(
      path.join(root, 'alpha.test.ts'),
      `import { test } from 'vitest';
console.log('module output');
test('passing', () => console.log('alpha output'));
test('failing', () => {
  const error = new Error('primary failure');
  error.stack = 'Error: stack donor';
  throw error;
});
test.skip('pending', () => {});`,
    );
    await writeFile(
      path.join(root, 'beta.test.ts'),
      `import { test } from 'vitest';
test('passing', () => console.error('beta output'));`,
    );
    await writeFile(
      path.join(root, 'gamma.test.ts'),
      `import { beforeAll, describe, test } from 'vitest';
describe('broken suite', () => {
  beforeAll(() => {
    const error = new Error('setup failure');
    error.stack = 'Error: setup failure';
    throw error;
  });
  test('unreachable', () => {});
});`,
    );
    await writeFile(
      path.join(root, 'unnamed.test.ts'),
      `import { test } from 'vitest';
test('passing', () => console.log('unnamed output'));`,
    );
    exitCode = await runReporter(root, socketPath);
    await runReporter(root, socketPath, false);
  } finally {
    if (server.listening) {
      await new Promise<void>(resolve =>
        server.close(() => {
          resolve();
        }),
      );
    }
    await rm(root, { force: true, recursive: true });
  }
  const getRecording = (identifier: string) =>
    (recordings.get(identifier) ?? '')
      .replaceAll(path.relative(process.cwd(), root), '<root>')
      .replaceAll(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z/g, '<timestamp>');
  return {
    alpha: getRecording('example-alpha'),
    alphaConsole: getRecording('example-alpha-console'),
    beta: getRecording('example-beta'),
    betaConsole: getRecording('example-beta-console'),
    exitCode,
    gamma: getRecording('example-gamma'),
    unnamed: getRecording('example'),
    unnamedConsole: getRecording('example-console'),
  };
};

const createJournaldReporter = (options?: ConstructorParameters<typeof JournaldReporter>[0]) =>
  new JournaldReporter(options);

export const test = base
  .extend('createJournaldReporter', () => createJournaldReporter)
  .extend('errorSpy', ({}, { onCleanup }) => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(vi.fn());
    onCleanup(() => {
      errorSpy.mockRestore();
    });
    return errorSpy;
  })
  .extend('journalRun', () => runJournalScenario());

export { describe, expect } from 'vitest';
