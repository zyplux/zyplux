import type { SpawnOptions } from 'node:child_process';

import { ChildProcess, spawn } from 'node:child_process';
import { PassThrough, Writable } from 'node:stream';
import { vi } from 'vitest';

import { isPatternMatch } from './pattern-match.ts';
import { requireMockedModule } from './require-mocked-module.ts';

export type ShellCall = {
  argv: string[];
  cwd?: string;
  env?: Record<string, string | undefined>;
  program: string;
  stdin?: string;
};

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

type SpawnedReply = { exitCode: number; stdout: string };

const isCommandMatch = (command: string, pattern: RegExp | string) =>
  typeof pattern === 'string'
    ? command.startsWith(pattern) && (command.length === pattern.length || command[pattern.length] === ' ')
    : isPatternMatch(command, pattern);

const takeReply = ({ replies }: ShellRoute) => {
  const reply = replies.length > 1 ? replies.shift() : replies[0];
  if (reply === undefined) throw new Error('shell route has no replies left');
  return reply;
};

const envOverlay = (env: NodeJS.ProcessEnv = {}) => {
  const overlaid = Object.entries(env).filter(
    ([name, value]) => !Object.hasOwn(process.env, name) || process.env[name] !== value,
  );
  return overlaid.length === 0 ? undefined : Object.fromEntries(overlaid);
};

const createFakeChild = ({ exitCode, stdout: output }: SpawnedReply, onStdin: (text: string) => void) => {
  const stdout = new PassThrough();
  const stderr = new PassThrough();
  const written: Buffer[] = [];
  const stdin = new Writable({
    final: done => {
      onStdin(Buffer.concat(written).toString());
      done();
    },
    write: (chunk: Buffer, _encoding, done) => {
      written.push(Buffer.from(chunk));
      done();
    },
  });
  const child = Object.assign(new ChildProcess(), { stderr, stdin, stdout });

  let flowing = 2;
  const closeWhenDrained = () => {
    flowing -= 1;
    if (flowing === 0) child.emit('close', exitCode);
  };
  stdout.on('end', closeWhenDrained);
  stderr.on('end', closeWhenDrained);

  queueMicrotask(() => {
    stdout.end(output);
    stderr.end();
    stdout.resume();
    stderr.resume();
  });

  return child;
};

const silenceStandardStreams = () => {
  const silenced = [
    vi.spyOn(process.stdout, 'write').mockReturnValue(true),
    vi.spyOn(process.stderr, 'write').mockReturnValue(true),
  ];
  return () => {
    for (const stream of silenced) stream.mockRestore();
  };
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
    const reply = takeReply(route);
    const resolved = typeof reply === 'function' ? reply(command) : reply;
    return typeof resolved === 'string' ? { exitCode: 0, stdout: resolved } : resolved;
  };

  const spawnFake = (program: string, args: readonly string[] = [], options: SpawnOptions = {}) => {
    const argv = [...args];
    const command = [program, ...argv].join(' ');
    const overlay = envOverlay(options.env);
    const call: ShellCall = {
      argv,
      program,
      ...(typeof options.cwd === 'string' && { cwd: options.cwd }),
      ...(overlay !== undefined && { env: overlay }),
    };
    calls.push(call);
    commands.push(command);
    return createFakeChild(resolveReply(command), text => {
      call.stdin = text;
    });
  };

  return {
    calls,
    commands,
    commandsMatching: pattern => commands.filter(command => isCommandMatch(command, pattern)),
    install: () => {
      requireMockedModule(spawn, 'node:child_process', 'spawn');
      const spawnMock = vi.mocked(spawn);
      spawnMock.mockImplementation(spawnFake);
      const restoreStreams = silenceStandardStreams();
      return () => {
        restoreStreams();
        spawnMock.mockReset();
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
