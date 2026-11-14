import { describe, expect, test } from './fakes.ts';

const USAGE_EXIT_CODE = 2;

describe('1.1 running a CLI', () => {
  test('1.1.1 a CLI runner captures output and reports the requested exit code', ({
    createCliExitError,
    createCliRunner,
    createConsoleCapture,
  }) => {
    const logs = createConsoleCapture();
    const restore = logs.install();
    const cli = createCliRunner((args, io) => {
      io.stdout(args.join(' '));
      io.stderr('invalid request');
      return io.onExit(USAGE_EXIT_CODE);
    });
    try {
      expect(() => cli.run('inspect', 'config')).toThrow(createCliExitError(USAGE_EXIT_CODE));
      expect(logs).toHaveLogged('inspect config');
      expect(logs).toHaveErrored('invalid request');
      expect(logs).not.toHaveWarned();
      expect(() => {
        expect(logs).toHaveWarned();
      }).toThrow('console.warn lines: (none)');
    } finally {
      restore();
    }
  });
});

describe('1.2 routing network requests', () => {
  test('1.2.1 fetch routing accepts URL and Request inputs and restores the real fetch', async ({
    createFetchFake,
  }) => {
    const originalFetch = globalThis.fetch;
    const network = createFetchFake();
    const restore = network.install();
    network.on('https://example.test/', () => Response.json('prefix'));
    network.on(/\/specific$/, () => Response.json('specific'));
    network.otherwise(() => Response.json('fallback'));
    try {
      const specificResponse = await fetch(new URL('https://example.test/specific'));
      const prefixResponse = await fetch(new Request('https://example.test/other'));
      const fallbackResponse = await fetch('https://other.test/');
      expect(await specificResponse.json()).toBe('specific');
      expect(await prefixResponse.json()).toBe('prefix');
      expect(await fallbackResponse.json()).toBe('fallback');
      expect(network.requests).toEqual([
        'https://example.test/specific',
        'https://example.test/other',
        'https://other.test/',
      ]);
    } finally {
      restore();
    }
    expect(globalThis.fetch).toBe(originalFetch);
  });
});

describe('1.3 requiring shell mock setup', () => {
  test('1.3.1 a shell fake explains the required mock when its module is unmocked', ({ createShellFake }) => {
    expect(() => createShellFake().install()).toThrow('node:child_process is not mocked');
  });
});

describe('1.4 answering terminal questions', () => {
  test('1.4.1 records questions and answers with an empty string', async ({ askQuestion, createPromptFake }) => {
    const prompt = createPromptFake();
    const restore = prompt.install();
    try {
      expect(await askQuestion('Continue?')).toBe('');
      expect(prompt.messages).toEqual(['Continue?']);
    } finally {
      restore();
    }
  });
});
