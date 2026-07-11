import { isDeepStrictEqual } from 'node:util';
import { expect } from 'vitest';

import type { ConsoleCapture } from './console';
import type { ShellFake } from './shell';

import { isPatternMatch } from './pattern-match';

export type LineMatch = RegExp | string;

export const registerMatchers = <Registered extends Parameters<typeof expect.extend>[0]>(matchers: Registered) => {
  expect.extend(matchers);
  return matchers;
};

const isLineMatch = (line: string, expected: LineMatch) =>
  typeof expected === 'string' ? line === expected : isPatternMatch(line, expected);

const renderLines = (label: string, lines: string[]) =>
  lines.length === 0 ? `${label}: (none)` : `${label}:\n${lines.map(line => `  ${line}`).join('\n')}`;

const lineListResult = (lines: string[], label: string, expected: LineMatch | undefined) => {
  const isPass = expected === undefined ? lines.length > 0 : lines.some(line => isLineMatch(line, expected));
  const observation =
    expected === undefined
      ? `${label} were ${isPass ? 'captured' : 'empty'}`
      : `${label} ${isPass ? 'include' : 'do not include'} ${String(expected)}`;
  return { message: () => `${observation}\n${renderLines(label, lines)}`, pass: isPass };
};

const unmatchedElements = (received: readonly unknown[], expected: readonly unknown[]) => {
  const remaining = [...expected];
  return received.filter(item => {
    const index = remaining.findIndex(candidate => isDeepStrictEqual(candidate, item));
    if (index === -1) return true;
    remaining.splice(index, 1);
    return false;
  });
};

export const storyMatchers = registerMatchers({
  toContainExactElementsInAnyOrder: (received: readonly unknown[], expected: readonly unknown[]) => {
    const extra = unmatchedElements(received, expected);
    const missing = unmatchedElements(expected, received);
    return {
      message: () =>
        `expected [${received.join(', ')}] to contain exactly [${expected.join(', ')}] in any order\n` +
        `${renderLines('missing', missing.map(String))}\n${renderLines('extra', extra.map(String))}`,
      pass: extra.length === 0 && missing.length === 0,
    };
  },
  toContainNoDuplicates: (received: readonly unknown[]) => {
    const duplicates = received.filter(
      (item, index) => received.findIndex(candidate => isDeepStrictEqual(candidate, item)) !== index,
    );
    return {
      message: () =>
        `expected [${received.join(', ')}] to contain no duplicates\n${renderLines('duplicates', duplicates.map(String))}`,
      pass: duplicates.length === 0,
    };
  },
  toHaveErrored: ({ errorLines }: ConsoleCapture, line?: LineMatch) =>
    lineListResult(errorLines, 'console.error lines', line),
  toHaveLogged: ({ logLines }: ConsoleCapture, line?: LineMatch) => lineListResult(logLines, 'console.log lines', line),
  toHaveRun: ({ commands }: ShellFake, command: string) => ({
    message: () =>
      `the shell ${commands.includes(command) ? 'ran' : 'never ran'} ${command}\n${renderLines('commands', commands)}`,
    pass: commands.includes(command),
  }),
  toHaveRunMatching: (shell: ShellFake, pattern: RegExp | string) => {
    const matched = shell.commandsMatching(pattern);
    return {
      message: () =>
        `${matched.length} shell commands matched ${String(pattern)}\n${renderLines('commands', shell.commands)}`,
      pass: matched.length > 0,
    };
  },
  toHaveWarned: ({ warnLines }: ConsoleCapture, line?: LineMatch) =>
    lineListResult(warnLines, 'console.warn lines', line),
});

declare module 'vitest' {
  interface Matchers<T> {
    toContainExactElementsInAnyOrder: (expected: readonly unknown[]) => T;
    toContainNoDuplicates: () => T;
    toHaveErrored: (line?: LineMatch) => T;
    toHaveLogged: (line?: LineMatch) => T;
    toHaveRun: (command: string) => T;
    toHaveRunMatching: (pattern: RegExp | string) => T;
    toHaveWarned: (line?: LineMatch) => T;
  }
}
