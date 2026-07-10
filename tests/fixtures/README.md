# @zyplux/tests-fixtures

Story-test fixtures for code built on Bun and `@zyplux/util`. Fakes swap in at the lowest boundary (`Bun.$`, `fetch`, `console`, `prompt`, `Bun.sleep`, `process.env`) so tests exercise only public interfaces. Ships TypeScript source, consumed directly under Bun.

## Install

```sh
bun add -d @zyplux/tests-fixtures
```

## Use

Pick a base per app type, extend it with suite fixtures, and keep the binding named `test`:

```ts
import { cliTest } from '@zyplux/tests-fixtures';

export const test = cliTest;
export { describe, expect } from 'vitest';
```

```ts
import { describe, expect, test } from '#fixtures';

describe('1.1 pushing a branch', () => {
  test('1.1.1 pushes and reports the PR url', async ({ logs, shell }) => {
    shell.on('git rev-parse --abbrev-ref HEAD', 'feat-x');
    shell.on('git push', '');

    await runPushBranch({ command: 'push-branch', hold: false, ready: false });

    expect(shell).toHaveRun('git push --set-upstream origin feat-x');
    expect(logs).toHaveLogged('PR (draft): https://github.com/acme/repo/pull/1');
  });
});
```

## Bases

- `libraryTest` — lazy fixtures: `shell` (fake `Bun.$`, installed only when destructured), `tempDir` (auto-removed scratch directory with `path`, `write`, `exists`).
- `cliTest` — extends `libraryTest`; auto-silences and captures `console` (`logs`), makes `Bun.sleep` instant; adds lazy `network` (fake `fetch`), `prompt` (fake `globalThis.prompt` that accepts and records every message), and `env` (`set(name, value)` stubs an env var for the test).

## Fakes

- `createShellFake()` — routes commands (`on(pattern, ...replies)`, later routes win, the last reply repeats; `otherwise(reply)` sets a fallback, unrouted commands throw) and records `calls` (`{ argv, program }`), `commands` (rendered strings), `commandsMatching(pattern)`.
- `createConsoleCapture()` — records `logLines`/`warnLines`/`errorLines`.
- `createFetchFake()` — routes urls (`on(prefixOrRegExp, reply)`, `otherwise(reply)`) and records `requests`; `okResponse()`/`notFoundResponse()` build replies.
- `createPromptFake()` — accepts every `prompt()` call and records `messages`.
- `createTempDir()` — `path`, `write(relativePath, content)`, `exists(relativePath)`, `remove()`.
- `fakeShellOutput(stdout, exitCode?)`, `fakeShellPromise(result)`, `toArgv(values)` — raw `Bun.$` doubles behind `createShellFake`.

## Matchers

Importing a base registers domain matchers via `expect.extend`:

- `expect(shell).toHaveRun(command)` — the exact rendered command ran.
- `expect(shell).toHaveRunMatching(pattern)` — some command matches (string = command prefix at a word boundary, same as `on`; RegExp = test); negate with `.not` for "never ran".
- `expect(logs).toHaveLogged(line?)` / `toHaveWarned(line?)` / `toHaveErrored(line?)` — a captured line equals the string (or matches the RegExp); with no argument, that the channel captured anything, so `.not.toHaveWarned()` asserts silence.
