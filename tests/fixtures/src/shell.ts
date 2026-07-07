import type { $ } from '@zyplux/util';

import { vi } from 'vitest';

type ShellOutput = Awaited<ReturnType<typeof $.git.status>>;
type ShellPromise = ReturnType<typeof Bun.$>;
type ShellValue = Parameters<typeof Bun.$>[1];

const notImplemented = (method: string) => () => {
  throw new Error(`fakeShellOutput.${method} is not implemented`);
};

export const fakeShellOutput = (stdout: string, exitCode = 0): ShellOutput => ({
  arrayBuffer: notImplemented('arrayBuffer'),
  blob: notImplemented('blob'),
  bytes: notImplemented('bytes'),
  exitCode,
  json: notImplemented('json'),
  stderr: Buffer.alloc(0),
  stdout: Buffer.from(stdout),
  text: () => stdout,
});

export const fakeShellPromise = (result: ShellOutput): ShellPromise => {
  const chainMethod = () => promise;
  const promise: ShellPromise = Object.assign(Promise.resolve(result), {
    arrayBuffer: notImplemented('arrayBuffer'),
    blob: notImplemented('blob'),
    cwd: chainMethod,
    env: chainMethod,
    json: notImplemented('json'),
    lines: notImplemented('lines'),
    nothrow: chainMethod,
    quiet: chainMethod,
    stdin: new WritableStream(),
    text: (encoding?: BufferEncoding) => Promise.resolve(result.text(encoding)),
    throws: chainMethod,
  }) satisfies ShellPromise;
  return promise;
};

export const toArgv = (values: ShellValue[]) => (Array.isArray(values[0]) ? values[0].map(String) : []);

const renderValue = (value: ShellValue): string => {
  if (Buffer.isBuffer(value)) return value.toString();
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    const items: ShellValue[] = value;
    return items.map(item => renderValue(item)).join(' ');
  }
  throw new Error('unexpected shell expression in renderCommand');
};

const renderCommand = (strings: TemplateStringsArray, values: ShellValue[]) =>
  strings
    .reduce((rendered, chunk, index) => {
      const value = values[index];
      return `${rendered}${chunk}${value === undefined ? '' : renderValue(value)}`;
    }, '')
    .trim();

export type ShellCall = { argv: string[]; program: string };
export type ShellFake = {
  calls: ShellCall[];
  commands: string[];
  commandsMatching: (pattern: RegExp | string) => string[];
  install: () => () => void;
  on: (pattern: RegExp | string, ...replies: [ShellReply, ...ShellReply[]]) => void;
  otherwise: (...replies: [ShellReply, ...ShellReply[]]) => void;
};

export type ShellReply = ((command: string) => string) | string | { exitCode: number; stdout: string };

type ShellRoute = { pattern: RegExp | string; replies: ShellReply[] };

const isCommandMatch = (command: string, pattern: RegExp | string) => {
  if (typeof pattern === 'string') {
    if (!command.startsWith(pattern)) return false;
    return command.length === pattern.length || command[pattern.length] === ' ';
  }
  return pattern.test(command);
};

const takeReply = ({ replies }: ShellRoute) => {
  const reply = replies.length > 1 ? replies.shift() : replies[0];
  if (reply === undefined) throw new Error('shell route has no replies left');
  return reply;
};

export const createShellFake = (): ShellFake => {
  const calls: ShellCall[] = [];
  const commands: string[] = [];
  const routes: ShellRoute[] = [];
  let fallback: ShellRoute | undefined;

  const resolveReply = (command: string) => {
    const route = routes.findLast(candidate => isCommandMatch(command, candidate.pattern)) ?? fallback;
    if (route === undefined) {
      const registered = routes.map(known => `  ${String(known.pattern)}`).join('\n');
      throw new Error(`no shell route matches: ${command}\nregistered routes:\n${registered}`);
    }
    return takeReply(route);
  };

  const shellFn = vi.fn<typeof Bun.$>();
  shellFn.mockImplementation((strings, ...values) => {
    const command = renderCommand(strings, values);
    calls.push({ argv: toArgv(values), program: strings[0]?.trim().split(' ', 1)[0] ?? '' });
    commands.push(command);
    const reply = resolveReply(command);
    const resolved = typeof reply === 'function' ? reply(command) : reply;
    const output = typeof resolved === 'string' ? fakeShellOutput(resolved) : fakeShellOutput(resolved.stdout, resolved.exitCode);
    return fakeShellPromise(output);
  });

  return {
    calls,
    commands,
    commandsMatching: pattern => commands.filter(command => isCommandMatch(command, pattern)),
    install: () => {
      const original = Bun.$;
      Bun.$ = shellFn;
      return () => {
        Bun.$ = original;
      };
    },
    on: (pattern, ...replies) => {
      routes.push({ pattern, replies: [...replies] });
    },
    otherwise: (...replies) => {
      fallback = { pattern: '', replies: [...replies] };
    },
  };
};
