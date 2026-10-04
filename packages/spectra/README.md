# @zyplux/spectra

Shared Vitest fixtures, matchers, polling, and journal reporting for Node CLIs and libraries. Fakes swap in at the lowest boundary (`node:child_process`, `node:readline/promises`, `node:timers/promises`, `fetch`, `console`, `process.env`) so tests exercise only public interfaces.

## Install

```sh
pnpm add -D @zyplux/spectra
```

Each fake needs the Node module it stands in for mocked in that project's own vitest setup file — only the modules whose fakes you use:

```ts
import { vi } from 'vitest';

vi.mock('node:child_process', async importOriginal => {
  const actual = await importOriginal<typeof import('node:child_process')>();
  return { ...actual, spawn: vi.fn(actual.spawn) }; // shell fake
});
// node:readline/promises -> createInterface (prompt fake); node:timers/promises -> setTimeout (instant sleeps)
```

Each factory wraps the original, so the module stays fully live until a fake installs an implementation. A fake whose module is unmocked says which one to add.

## Use

Each story domain has a named fixture module, such as `stories/repositories/repositories.ts`. Extend a base with the subjects that its tests need:

```ts
import { runPushBranch } from '@example/app';
import { cliTest } from '@zyplux/spectra';

export const test = cliTest.extend('runPushBranch', () => runPushBranch);
export { describe, expect } from 'vitest';
```

```ts
import { describe, expect, test } from './repositories.ts';

describe('1.1 pushing a branch', () => {
  test('1.1.1 pushes and reports the PR url', async ({ logs, runPushBranch, shell }) => {
    shell.on('git rev-parse --abbrev-ref HEAD', 'feat-x');
    shell.on('git push', '');

    await runPushBranch({ command: 'push-branch', hold: false, ready: false });

    expect(shell).toHaveRun('git push --set-upstream origin feat-x');
    expect(logs).toHaveLogged('PR (draft): https://github.com/acme/repo/pull/1');
  });
});
```

## Entry points

Test tools share the root import. The reporter has a separate entry point because it loads in Vitest's configuration before the test context exists.

| Import path after `@zyplux/spectra` | Purpose |
| --- | --- |
| Root | Vitest bases, fixtures, fakes, helpers, console capture, and matchers |
| `/reporters` | Record Vitest results and console output in systemd's journal |
| `/package.json` | Package metadata |

Internal helpers stay beside the tools that use them: pattern matching and module mock validation live in `helpers`; journal stream writing lives in `reporters`.

## Bases

- `libraryTest` — lazy fixtures: `shell` (fake `node:child_process` spawn, installed only when destructured), `tempDir` (auto-removed scratch directory with `path`, `write`, `exists`).
- `cliTest` — extends `libraryTest`; automatically captures and silences `console` (`logs`), makes `node:timers/promises` sleeps instant, and installs `network` (fake `fetch`). It adds lazy `prompt` (fake `node:readline/promises` interface that records every question and answers with an empty string) and `env` (`set(name, value)` stubs an env var for the test).

## Fakes and helpers

- `createShellFake()` — routes commands (`on(pattern, ...replies)`, later routes win, the last reply repeats; `otherwise(reply)` sets a fallback, unrouted commands throw) and records `calls` (`{ argv, cwd?, env?, program, stdin? }`), `commands` (rendered strings), `commandsMatching(pattern)`.
- `createConsoleCapture()` — records `logLines`/`warnLines`/`errorLines`.
- `createFetchFake()` — routes urls (`on(prefixOrRegExp, reply)`, `otherwise(reply)`) and records `requests`; `okResponse()`/`notFoundResponse()` build replies.
- `createPromptFake()` — records `question()` messages and immediately returns an empty string, simulating Enter without typed input. It lets tests exercise terminal prompts without waiting for keyboard input.
- `createTempDir()` — `path`, `write(relativePath, content)`, `exists(relativePath)`, `remove()`.

## Matchers

Importing a base registers domain matchers via `expect.extend`:

- `expect(shell).toHaveRun(command)` — the exact rendered command ran.
- `expect(shell).toHaveRunMatching(pattern)` — some command matches (string = command prefix at a word boundary, same as `on`; RegExp = test); negate with `.not` for "never ran".
- `expect(logs).toHaveLogged(line?)` / `toHaveWarned(line?)` / `toHaveErrored(line?)` — a captured line equals the string (or matches the RegExp); with no argument, that the channel captured anything, so `.not.toHaveWarned()` asserts silence.
- `expect(items).toContainExactElementsInAnyOrder(expected)` — nested elements match regardless of order, including duplicate counts.
- `expect(items).toContainNoDuplicates()` — no two elements are deeply equal.
- `expect(items).toHaveNumberOfElements(count)` — the collection has exactly that many elements.

## Polling

`pollUntil(condition, { timeout, interval?, grace? })` waits for an asynchronous condition using Vitest's `expect.poll`. The condition receives an abort signal. A grace period requires a second matching observation after that delay. The return is `{ settled, error }`; deadlines also bound pending observations and grace periods.

## Journal reporting

Add the reporter alongside Vitest's normal terminal reporters:

```ts
import { JournaldReporter } from '@zyplux/spectra/reporters';
import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    reporters: [...configDefaults.reporters, new JournaldReporter({ identifier: 'my-repo' })],
  },
});
```

Named projects record summaries and failure details under `my-repo-<project>`; console messages use `my-repo-<project>-console`. Unnamed projects use `my-repo` and `my-repo-console`. Read them with `journalctl -t my-repo-<project>`. Recording is enabled when the systemd journal socket exists. The `isEnabled` option explicitly controls recording; connection errors are reported to the terminal.

The optional `socketPath` selects a journal stream socket; its default is `/run/systemd/journal/stdout`.
