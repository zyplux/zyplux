# Plan: knip governance + TS export-boundary discipline

**Status: implemented in `zyplux` itself** (new `knip-config` cerberus check,
widened `lib-ts-tests` gate, `knip.json`/`knip.prod.json`, doubled
`knip` justfile recipe — all uncommitted, pending review). Not yet rolled out
to `zyp-vps`/`zyp`/`zyp-ocr`/`zyplux-ai`/`totchef` — see Sequencing.

## Origin

`zyp-vps/packages/connector-web/src/index.ts` re-exported `verifyHostJwt` (zero
consumers anywhere) and `createHostJwtVerifier` (consumed only by its own test
package). `knip` reported clean. Root cause: knip's `includeEntryExports`
defaults off, exempting a package's `exports`-map entry file from unused-export
reporting — correct for a genuinely published package, wrong for a
`"private": true` workspace-internal one nothing outside the monorepo can ever
import. This generalizes to three enforceable rules, and relates to the existing
`docs/roadmap/next.md` "ts testing / cz" item — though `apps/cz` turned out to
already be compliant (its `exports` map is already root-only; `deps-catalog.ts`/
`release-targets.ts` are only reachable via its own `#`-prefixed internal
`imports` map, which isn't part of the public surface and every story test
already goes through `#fixtures` — confirmed by running the widened check
against the real repo, zero findings).

## Rule 1 — no inline knip config, governed `knip.json`

- No repo may set `package.json`'s `"knip"` key. Hard rule, no exceptions.
- A standalone `knip.json` is optional; a new cerberus check validates its
  shape against an allowlist (`ALLOWED_KNIP` constant in the check module,
  keyed by repo — no existing repo-scoped-allowlist idiom exists in cerberus
  today; closest precedent is `ruff_config_check.py`'s value-scoped
  `SANCTIONED_IGNORE`, generalized to repo-scoped here).
- Every repo also gets a second config, `knip.prod.json`
  (`includeEntryExports: true` + `ignoreWorkspaces: ["tests/*"]`), run via a
  second `knip --config knip.prod.json` step in the `knip` justfile
  recipe. Verified empirically: this catches dead exports and test-only-consumed
  exports without weakening the normal run — the base run still fully checks
  test workspaces' own unused files/deps. Per-workspace `includeEntryExports:
  false` overrides must exactly match the repo's npm-kind `release-targets.toml`
  entries (missing file ⇒ no overrides, nothing is exempt).
- **Implementation wrinkle found while building this**: `knip --config` replaces
  the config wholesale rather than layering on `knip.json` (knip has no
  `extends`). So `knip.prod.json` must also repeat the repo's
  allowlisted `knip.json` content verbatim (e.g. `zyplux`'s `ignoreBinaries`) —
  the check validates both files against the same `ALLOWED_KNIP_JSON` entry.

**Allowlist entries confirmed legitimate** (verified against knip's real
plugin source and empirically against each repo, entry overrides stripped):

| repo | entry | why it's real, not stale |
|---|---|---|
| `zyp` | `apps/web`: `src/frontend.tsx` | Bun's native HTML-import bundler (`Bun.serve({routes...})`) — knip has no plugin for it, unlike Vite. `src/index.html` in the same override is inert (`.html` is a foreign extension to knip) and can be dropped. |
| `zyp-ocr` | `apps/web`: `src/contracts.ts` | standard knip pattern — declares schema exports as public surface, unrelated to reachability. |
| `zyp-ocr` | `apps/web`: `worker-configuration.d.ts`, `ignoreDependencies: ["cloudflare"]` | ambient `declare global` file (no import edges) plus knip having no `cloudflare:` protocol recognition (only `node:` is hardcoded). |
| `zyplux` | `ignoreBinaries: ["podman", "uv"]` | non-npm CLIs invoked from scripts, not resolvable via `package.json` deps. |

**Not real gaps — fix instead of allowlisting:**

- `zyplux-ai`'s `apps/web` override (`src/routes/**`, `src/router.tsx`) is
  **fully redundant today** — TanStack Router's committed `routeTree.gen.ts`
  already type-imports `router.tsx` and re-exports every route, which the
  already-auto-detected `tanstack-router` plugin entry makes reachable with
  zero config. Delete the override.
- `zyp-ocr`'s `router.tsx`/`src/routes/**/*.{ts,tsx}` entries exist only
  because `routeTree.gen.ts` is gitignored there (unlike `zyplux-ai`/`zyp-vps`,
  which commit it) — knip respects `.gitignore` by default. **Commit
  `routeTree.gen.ts`**, then drop those two entries; keep `contracts.ts` +
  the worker/cloudflare entries (real gaps, above).
- `totchef`'s inline `{"ignore": ["reference_clones/**"]}` goes away once
  `reference_clones` no longer lives inside any repo (per plan) — no allowlist
  entry needed once that move happens and it's folded into org governance.

## Rule 2 — root-only exports (`.` and `./package.json` only)

- Reuses existing machinery almost entirely: `test_seam.py`'s
  `_check_exports_surface` already enforces exactly this shape; it's just
  gated by `lib_ts_tests_check.py`'s `_is_library()`, which currently exempts
  private packages (`not manifest.get("private")`).
- **Change the gate, precisely**: dropping the `private` check outright would
  also wrongly pull in test-harness leaf packages (e.g. `tests/cz` — private,
  no exports, nothing ever imports it — existing test coverage,
  `test_21_1_4`, relies on this staying exempt). The correct fix: for members
  **outside** `tests/`, `private` no longer matters (a workspace-internal deep
  import doesn't care whether the target is private); for members **inside**
  `tests/`, keep the existing `not private` logic unchanged (`tests/fixtures`,
  a genuinely published library that happens to live under `tests/`, stays
  checked; harness-only packages stay exempt). Verified against the real repo:
  zyplux has no private packages outside `tests/` today, so this is a pure
  mechanism fix with zero behavior change for `zyplux` itself — it only bites
  once rolled out to repos like `zyp-vps`.
- **Strict, no curated-subpath allowlist** (decided): every non-published
  package exports only `.`, full stop. CSS/asset entries (e.g. `./theme.css`)
  stay exempt as a technical necessity — `index.ts` cannot re-export a
  stylesheet — not a policy carve-out.
- TypeScript's own module resolution (bundler mode, root-only exports map, no
  `paths` escape hatch anywhere in the org) already rejects deep cross-package
  imports at compile time once a package is root-only — confirmed empirically
  via `ts.resolveModuleName`. So Rule 2 needs **no new eslint rule and no new
  cerberus import-boundary check** — governing the exports-map shape is
  sufficient; TS makes deep imports uncompilable as a side effect.
- **Known restructuring needed once rolled out** (all currently private, all
  in repos with no `release-targets.toml`, so all newly in scope):
  - `zyplux-ai/packages/ui` (`@zyplux/ui`) — 10 curated subpaths, no `.` root
    at all today. Largest restructure.
  - `zyplux-ai/packages/mdx` (`@zyplux/mdx`) — one extra subpath
    (`./remark-preset`).
  - `zyp/packages/core` (`@totvibe/core`) — one extra subpath (`./ai-core`).

## Sequencing

1. `zyplux`: build both cerberus checks (knip config governance, widened
   root-seam gate) + the `knip.prod.json` convention. **Done** —
   `apps/cz` needed no changes, already compliant.
2. `zyp-vps`: adopt both checks — fixes `connector-web` (delete `verifyHostJwt`,
   move `createHostJwtVerifier` off the public root) as the case that started
   this.
3. `zyp-ocr`: commit `routeTree.gen.ts`, trim its knip override, adopt checks.
4. `zyplux-ai`: delete its redundant knip override, adopt checks, restructure
   `@zyplux/ui`/`@zyplux/mdx`.
5. `zyp`: adopt checks, restructure `@totvibe/core`.
6. `totchef`: after relocation into org governance and `reference_clones`
   removal.

## Left for implementation time

- Exact `ALLOWED_KNIP` data shape and where release-targets.toml parsing
  gets shared (a new small module, or inlined per check).
- justfile recipe wording for the second knip invocation
  (`justfile_check.py`'s canonical-baseline + `# CUSTOM`-marker convention
  is the likely fit).
