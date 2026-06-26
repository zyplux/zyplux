# @zyplux/util

Small Bun utilities — assertions, polling, bounded-concurrency mapping, zod-validated JSON reads, repo-URL normalization, `package.json`/`pyproject.toml` manifest schemas, and a `git`/`gh` shell harness. Ships TypeScript source, consumed directly under Bun.

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

- `parseJson` parses a JSON string and validates it against a zod schema — the primitive `readJson`/`readJsonSync` build on, for text you already hold (a subprocess's stdout, an env var).
- `readJson` / `readJsonSync` validate a JSON file against a zod schema (async via `Bun.file`, sync via `node:fs`); both throw on a missing file or bad shape.
- `http` is a ky-style client (`http.get(url)`, `.post`, …) whose `ResponsePromise` exposes `.json(schema)`, `.text()`, and `.response()`. It throws `FetchError` (carrying the `Response`) on a non-ok status and a `ZodError` on a bad shape, so consumers can catch or react rather than guess at a swallowed `undefined`.
- `poll` retries an async probe until it returns a defined value or the attempts run out; `mapWithConcurrency` maps over items with a fixed worker limit, preserving input order.
- `normalizeRepoUrl` reduces the many shapes a VCS url takes (`git+https`, `git@host:owner/repo`, `github:owner/repo`, bare `host/owner/repo`, `…/tree/main/sub`) to a canonical `https://host/owner/repo`, or `undefined` when the value is not a repository.
- `$` is `Bun.$` augmented with typed `git`/`gh` helpers, without mutating the global `Bun.$`.
- `@zyplux/util/schema` exports reusable structural zod primitives (`StringRecordSchema`, `LooseRecordSchema`, `StringArraySchema`, `UnknownArraySchema`, `UnknownArrayRecordSchema`, `IdSchema`, `VersionKeySchema`) that other schema modules compose from.
- `@zyplux/util/manifest` exports tolerant zod schemas (`PackageJsonSchema`, `PyProjectSchema`) and inferred types for reading `package.json` (incl. bun `workspaces`/`catalog`) and `pyproject.toml` (PEP 621 + PEP 735 + uv) manifests, dependency-name extractors (`npmDependencyNames`, `pythonRequirementNames`, `repositoryUrl`, `normalizePythonName`), and `findManifests(dir)`, which lists `git`-tracked manifests across one or many repos under `dir` (so `.gitignore` decides what is skipped — no node_modules, no build output, no untracked clones).
