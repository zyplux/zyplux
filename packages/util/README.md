# @zyplux/util

Small Bun utilities — assertions, polling, bounded-concurrency mapping, zod-validated JSON parsing (from a string, a file, or a URL) and TOML parsing (from a string), repo-URL normalization, `package.json`/`pyproject.toml` manifest schemas, and a `git`/`gh` shell harness. Ships TypeScript source, consumed directly under Bun.

## Install

```sh
bun add @zyplux/util zod
```

## Use

```ts
import { ensure, FetchError, http, mapWithConcurrency, normalizeRepoUrl, parseJson, poll, readJson, readJsonSync } from '@zyplux/util';
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

- `parseJson` / `parseToml` parse a string and validate it against a zod schema (throwing on bad syntax or shape), for text you already hold (a subprocess's stdout, a manifest you read); `readJson` / `readJsonSync` do the same from a JSON file (async via `Bun.file`, sync via `node:fs`).
- `tryParseJson` / `tryParseToml` are the tolerant siblings: they parse-and-validate but return the value or `undefined` on any failure (bad syntax or shape), so a caller scanning many files reads `const pkg = tryParseJson(text, Schema); if (pkg === undefined) continue;` with no result-unwrapping. When you want the error rather than just the value, wrap the strict parser yourself: `attempt(() => parseJson(text, Schema))`.
- `attempt(fn)` / `attemptAsync(fn)` run a thunk and fold its return or thrown error into a `SafeResult<T>` — `{ ok: true; data }` or `{ ok: false; error }`; they are the engine behind the tolerant helpers and the path to take when you want the error, not just the value, without a bare `catch`.
- `http` is a ky-style client (`http.get(url)`, `.post`, …) whose `ResponsePromise` exposes `.json(schema)`, `.text()`, and `.response()`. It throws `FetchError` (carrying the `Response`) on a non-ok status and a `ZodError` on a bad shape, so consumers can catch or react rather than guess at a swallowed `undefined`.
- `.safeJson(schema)` is the non-throwing sibling of `.json(schema)`, returning a `SafeResult<T>` but folding the fetch and non-ok status into it too.
- `fetchJson(url, schema)` is the tolerant convenience for the common best-effort case: a `GET` that resolves to the validated body or `undefined` on any failure (non-ok, network, or bad shape) — for remote data whose absence is a normal outcome rather than an error.
- `httpOk(url, init?)` resolves to whether a request returned a 2xx status (it `await`s `fetch` and reads `.ok`), for existence/availability checks where only the status matters and no body is read; pass `init` for headers or a `HEAD` method.
- `poll` retries an async probe until it returns a defined value or the attempts run out; `mapWithConcurrency` maps over items with a fixed worker limit, preserving input order.
- `normalizeRepoUrl` reduces the many shapes a VCS url takes (`git+https`, `git@host:owner/repo`, `github:owner/repo`, bare `host/owner/repo`, `…/tree/main/sub`) to a canonical `https://host/owner/repo`, or `undefined` when the value is not a repository.
- `$` is `Bun.$` augmented with typed `git`/`gh` helpers, without mutating the global `Bun.$`.
- `@zyplux/util/schema` exports reusable structural zod primitives (`StringRecordSchema`, `LooseRecordSchema`, `StringArraySchema`, `UnknownArraySchema`, `UnknownArrayRecordSchema`, `IdSchema`, `VersionKeySchema`) that other schema modules compose from.
- `@zyplux/util/manifest` exports tolerant zod schemas (`PackageJsonSchema`, `PyProjectSchema`) and inferred types for reading `package.json` (incl. bun `workspaces`/`catalog`) and `pyproject.toml` (PEP 621 + PEP 735 + uv) manifests, dependency-name extractors (`npmDependencyNames`, `pythonRequirementNames`, `repositoryUrl`, `normalizePythonName`), and `findManifests(dir)`, which lists `git`-tracked manifests across one or many repos under `dir` (so `.gitignore` decides what is skipped — no node_modules, no build output, no untracked clones).
