# @zyplux/util

Small utilities — assertions, polling, bounded-concurrency mapping, zod-validated JSON parsing (from a string, a file, or a URL) and TOML parsing (from a string), repo-URL normalization, `package.json`/`pyproject.toml` manifest schemas, and a `git`/`gh` shell harness. Ships compiled JS with type declarations, importable from Node 26.

## Install

```sh
pnpm add @zyplux/util zod
```

## Use

```ts
import { ensure } from '@zyplux/util/assert';
import { FetchError, http } from '@zyplux/util/http';
import { parseJson, readJson, readJsonSync } from '@zyplux/util/json';
import { $, readTrimmed } from '@zyplux/util/shell';
import * as z from 'zod';

const Pkg = z.object({ version: z.string() });
const { version } = await readJson(new URL('./package.json', import.meta.url), Pkg);
const { version: pinned } = readJsonSync(new URL('./package.json', import.meta.url), Pkg);
const config = parseJson(process.env['APP_CONFIG'] ?? '{}', Pkg);

const Health = z.object({ ok: z.boolean() });
try {
  const health = await http.get('https://example.com/health').json(Health);
} catch (error) {
  if (error instanceof FetchError && error.response.status === 404) {
    // react to a missing resource
  }
}

const branch = await readTrimmed($.git.revParse('HEAD', { abbrevRef: true }));
ensure(branch !== 'main', 'refusing to run on main');
```

- `parseJson` / `parseToml` parse a string and validate it against a zod schema (throwing on bad syntax or shape), for text you already hold (a subprocess's stdout, a manifest you read); `readJson` / `readJsonSync` do the same from a JSON file (async via `node:fs/promises`, sync via `node:fs`).
- `tryParseJson` / `tryParseToml` are the tolerant siblings: they parse-and-validate but return the value or `undefined` on any failure (bad syntax or shape), so a caller scanning many files reads `const pkg = tryParseJson(text, Schema); if (pkg === undefined) continue;` with no result-unwrapping. When you want the error rather than just the value, wrap the strict parser yourself: `attempt(() => parseJson(text, Schema))`.
- `attempt(fn)` / `attemptAsync(fn)` run a thunk and fold its return or thrown error into a `SafeResult<T>` — `{ ok: true; data }` or `{ ok: false; error }`; they are the engine behind the tolerant helpers and the path to take when you want the error, not just the value, without a bare `catch`.
- `http` is a ky-style client (`http.get(url)`, `.post`, …) whose `ResponsePromise` exposes `.json(schema)`, `.text()`, and `.response()`. It throws `FetchError` (carrying the `Response`) on a non-ok status and a `ZodError` on a bad shape, so consumers can catch or react rather than guess at a swallowed `undefined`.
- `.safeJson(schema)` is the non-throwing sibling of `.json(schema)`, returning a `SafeResult<T>` but folding the fetch and non-ok status into it too.
- `fetchJson(url, schema)` is the tolerant convenience for the common best-effort case: a `GET` that resolves to the validated body or `undefined` on any failure (non-ok, network, or bad shape) — for remote data whose absence is a normal outcome rather than an error.
- `isHttpOk(url, init?)` resolves to whether a request returned a 2xx status (it `await`s `fetch` and reads `.ok`), for existence/availability checks where only the status matters and no body is read; pass `init` for headers or a `HEAD` method.
- `poll(probe, options?)` retries an async probe. `until` stops on a match; `while` keeps retrying on a match. Each accepts a value compared with `Object.is`, or a synchronous predicate of the probe’s resolved result. These options are mutually exclusive; literal values must match the probe’s resolved return type or be `undefined`. With neither option, polling waits for any defined result. Defaults are five attempts, one second apart; `attempts` and `intervalMs` override them. It returns the matching result or `undefined` on exhaustion, without sleeping after the final attempt.
- `onExpiry` supplies an error message to throw when attempts are exhausted. With it, a default lookup returns a defined value; an explicit condition can still successfully match `undefined`. Without it, expiry returns `undefined`. Probe and predicate errors propagate immediately. Check the returned result separately when completing the wait does not guarantee that the operation succeeded.
- `mapWithConcurrency` maps over items with a fixed worker limit, preserving input order.
- `normalizeRepoUrl` reduces the many shapes a VCS url takes (`git+https`, `git@host:owner/repo`, `github:owner/repo`, bare `host/owner/repo`, `…/tree/main/sub`) to a canonical `https://host/owner/repo`, or `undefined` when the value is not a repository.
- `$` is a small shell-command harness with typed `git`/`gh` helpers.
- `runPassthrough(argv, cwd?)` from `@zyplux/util/exec` shares the parent's stdin, stdout, and stderr with a command, allowing interactive prompts and terminal detection. It resolves when the command succeeds and rejects on startup failure, a nonzero exit, or termination by a signal.
- `$.gh` reads return Zod-validated objects or arrays. Select supported fields with a nonempty `json` array, such as `$.gh.run.view(id, { json: ['status', 'conclusion'] })`; only those fields appear in the inferred result. PR draft flags are booleans, PR numbers and run IDs are numbers. Run conclusions preserve the empty string while pending.
- `$.gh.pr.reviews(slug, number)` returns reviews with author logins and commit IDs. `$.gh.release.exists(tag)` checks an exact tag, returning `false` for a missing release and propagating lookup errors. Actions return `Promise<void>`. Raw CLI commands remain available through `$`.
- `@zyplux/util/contracts` exports reusable structural zod primitives (`StringRecordSchema`, `LooseRecordSchema`, `StringArraySchema`, `UnknownArraySchema`, `UnknownArrayRecordSchema`, `IdSchema`, `VersionKeySchema`) that other schema modules compose from.
- `@zyplux/util/contracts` exports tolerant zod schemas (`PackageJsonSchema`, `PyProjectSchema`) and inferred types for reading `package.json` (incl. pnpm workspace/catalog) and `pyproject.toml` (PEP 621 + PEP 735 + uv) manifests; `@zyplux/util/manifest` exports dependency-name extractors (`npmDependencyNames`, `pythonRequirementNames`, `repositoryUrl`, `normalizePythonName`), and `findManifests(dir)`, which lists `git`-tracked manifests across one or many repos under `dir` (so `.gitignore` decides what is skipped — no node_modules, no build output, no untracked clones).

## Timing and source analysis

`LapTimer` is available from `@zyplux/util/lap-timer`. It measures named operations, nested laps, and concurrent operation arrays, preserving durations on failure. `timings` contains the named measurements; `timingsWithTotal` adds the elapsed total. `lapAndStop` completes a timer, and `importTimings` incorporates externally measured durations.

`@zyplux/util/module-references` exports `collectModuleReferences(sourceFile)`, which reads TypeScript imports and re-exports, including type-only and value bindings. Install the optional TypeScript peer to use it:

```sh
pnpm add typescript
```

`@zyplux/util/type-dependencies` exports `findTypeDependencyViolations({ imports, packages, sharedTypeSurfaces })`. It checks public package entries and type ownership using caller-supplied module references and package declarations. Repository-specific architecture policy stays with the consumer.

`@zyplux/util/workspace-architecture` discovers workspace packages. Its export-map and ownership helpers support conditional exports, blocked entries, wildcard subpaths, and nested package directories.
