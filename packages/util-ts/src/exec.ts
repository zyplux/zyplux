import { spawn } from 'node:child_process';
import { constants } from 'node:os';

const FAILURE_EXIT_CODE = 1;
const SIGNAL_EXIT_OFFSET = 128;

export type ExecPromise = Promise<ExecResult> & {
  cwd: (dir: string) => ExecPromise;
  env: (vars: Record<string, string | undefined>) => ExecPromise;
  nothrow: () => ExecPromise;
  quiet: () => ExecPromise;
  text: (encoding?: BufferEncoding) => Promise<string>;
};

export type ExecResult = {
  exitCode: number;
  stderr: Buffer;
  stdout: Buffer;
  text: (encoding?: BufferEncoding) => string;
};

type SpawnState = {
  cwd?: string;
  env?: Record<string, string | undefined>;
  nothrow: boolean;
  quiet: boolean;
  stdin?: Buffer | string;
};

export class ExecError extends Error {
  readonly exitCode: number;
  readonly stderr: Buffer;
  readonly stdout: Buffer;

  constructor(argv: string[], { exitCode, stderr, stdout }: ExecResult) {
    super(`command failed with exit code ${exitCode}: ${argv.join(' ')}`);
    this.name = 'ExecError';
    this.exitCode = exitCode;
    this.stdout = stdout;
    this.stderr = stderr;
  }
}

const toExecResult = (exitCode: number, stdout: Buffer, stderr: Buffer) => ({
  exitCode,
  stderr,
  stdout,
  text: (encoding: BufferEncoding = 'utf8') => stdout.toString(encoding),
});

const spawnProcess = (argv: string[], { cwd, env, nothrow, quiet, stdin }: SpawnState, shouldMerge: boolean) =>
  new Promise<ExecResult>((resolve, reject) => {
    const [command, ...args] = argv;
    if (command === undefined) {
      reject(new Error('run: argv must contain at least a command'));
      return;
    }

    const child = spawn(command, args, {
      cwd: cwd,
      env: env === undefined ? process.env : { ...process.env, ...env },
      stdio: [stdin === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'],
    });
    if (stdin !== undefined) child.stdin?.end(stdin);

    const merged: Buffer[] = [];
    const stdoutChunks: Buffer[] = [];
    const stderrChunks: Buffer[] = [];

    child.stdout?.on('data', (chunk: Buffer) => {
      (shouldMerge ? merged : stdoutChunks).push(chunk);
      if (!quiet) process.stdout.write(chunk);
    });
    child.stderr?.on('data', (chunk: Buffer) => {
      (shouldMerge ? merged : stderrChunks).push(chunk);
      if (!quiet) process.stderr.write(chunk);
    });

    child.on('error', reject);
    child.on('close', (code, signal) => {
      const exitCode = code ?? (signal === null ? FAILURE_EXIT_CODE : SIGNAL_EXIT_OFFSET + constants.signals[signal]);
      const result = toExecResult(
        exitCode,
        shouldMerge ? Buffer.concat(merged) : Buffer.concat(stdoutChunks),
        shouldMerge ? Buffer.alloc(0) : Buffer.concat(stderrChunks),
      );
      if (!nothrow && result.exitCode !== 0) {
        reject(new ExecError(argv, result));
        return;
      }
      resolve(result);
    });
  });

const makeExecPromise = (argv: string[], initial: Partial<SpawnState> = {}, shouldMerge = false) => {
  const state: SpawnState = { nothrow: false, quiet: false, ...initial };
  const spawnAfterChaining = async () => {
    await Promise.resolve();
    return spawnProcess(argv, state, shouldMerge);
  };

  const execPromise: ExecPromise = Object.assign(spawnAfterChaining(), {
    cwd: (dir: string) => {
      state.cwd = dir;
      return execPromise;
    },
    env: (vars: Record<string, string | undefined>) => {
      state.env = { ...state.env, ...vars };
      return execPromise;
    },
    nothrow: () => {
      state.nothrow = true;
      return execPromise;
    },
    quiet: () => {
      state.quiet = true;
      return execPromise;
    },
    text: async (encoding?: BufferEncoding) => {
      const result = await execPromise;
      return result.text(encoding);
    },
  });
  return execPromise;
};

export type RunOptions = {
  cwd?: string;
  env?: Record<string, string | undefined>;
  merge?: boolean;
  stdin?: Buffer | string;
};

export const run = (argv: string[], opts: RunOptions = {}): ExecPromise => {
  const { merge: shouldMerge = false, ...state } = opts;
  return makeExecPromise(argv, state, shouldMerge);
};

export const runPassthrough = ([program, ...args]: [string, ...string[]], cwd?: string) =>
  new Promise<void>((resolve, reject) => {
    const child = spawn(program, args, { cwd, stdio: 'inherit' });
    child.on('error', reject);
    child.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(`command failed with exit code ${code ?? 'unknown'}: ${[program, ...args].join(' ')}`));
    });
  });
