import type { $ } from '@zyplux/util/shell';

type ShellOutput = Awaited<ReturnType<typeof $.git.status>>;
type ShellPromise = ReturnType<typeof Bun.$>;

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

export const toArgv = (values: Parameters<typeof Bun.$>[1][]) =>
  Array.isArray(values[0]) ? values[0].map(String) : [];
