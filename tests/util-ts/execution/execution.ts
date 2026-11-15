import { libraryTest } from '@zyplux/spectra/library-test-api';
import { run, runPassthrough } from '@zyplux/util/exec';

const runWithParent = (script: string, stdin: string) => {
  const execUrl = import.meta.resolve('@zyplux/util/exec');
  const parent = `import { runPassthrough } from ${JSON.stringify(execUrl)};
    await runPassthrough([process.execPath, '-e', ${JSON.stringify(script)}]);`;
  return run([process.execPath, '--input-type=module', '--eval', parent], { stdin }).quiet();
};

export const test = libraryTest
  .extend('run', () => run)
  .extend('runPassthrough', () => runPassthrough)
  .extend('runWithParent', () => runWithParent);

export { describe, expect } from 'vitest';
