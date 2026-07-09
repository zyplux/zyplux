# 22. [Keeping zyplux-published artifacts at their latest release](test_22_zyplux_deps_latest.py)

The org publishes its own tooling — npm packages under the `@zyplux/` scope,
PyPI distributions named `zyplux-*`, and container images under
`ghcr.io/zyplux/` — and every repo must consume those at the latest published
release, or fixes never propagate. The `zyplux_deps_latest` bite
(`apps/cerberus/src/cerberus/checks/zyplux_latest_check.py`) detects usages by
namespace (never a hardcoded list, so future packages are auto-covered), reads
resolved and pinned versions — `bun.lock`, `uv.lock`, `==` pins in the
justfile and workflows, image tags in workflows and the justfile — and
compares each against the registry's latest via the `registries` module
(`apps/cerberus/src/cerberus/registries.py`). There is no `--fix`: bumping is
repo tooling's job, so lag findings point at `just upgrade`.

## 22.1 detecting zyplux artifacts by namespace

Only registry-published zyplux artifacts count as usages; a repo that consumes
none makes no registry request at all.

### 22.1.1 passes a repo that uses no zyplux published artifacts

A repo whose lockfiles, justfile, and workflows reference no `@zyplux/`,
`zyplux-*`, or `ghcr.io/zyplux/` artifact passes without a single registry
lookup.

### 22.1.2 ignores workspace local zyplux packages

`workspace:*` entries in `bun.lock` and editable/virtual sources in `uv.lock`
are the repo's own workspace members, not published consumption — they are
never compared and never queried.

### 22.1.3 queries each artifact once per run

An artifact referenced from several locations (e.g. the same image tag in two
workflows) is looked up exactly once; lookups for distinct artifacts run
concurrently off a shared result map.

## 22.2 keeping npm packages at the latest release

Resolved versions in `bun.lock` are the consumption truth for the JS
workspace.

### 22.2.1 passes when the locked npm version is the latest

A `bun.lock` that resolves an `@zyplux/` package to exactly the registry's
`dist-tags.latest` produces no finding.

### 22.2.2 fails naming the package versions and location when the lock lags

When `bun.lock` resolves an `@zyplux/` package below `dist-tags.latest`, the
check fails naming the package, the used and latest versions, the file it was
found in, and points at `just upgrade`.

## 22.3 keeping pypi distributions at the latest release

Locked versions in `uv.lock` and explicit `==` pins in the justfile or
workflows are compared against PyPI's `info.version`.

### 22.3.1 fails when uv lock resolves an outdated zyplux distribution

A `uv.lock` registry entry for a `zyplux-*` distribution below the latest
PyPI release fails the check.

### 22.3.2 fails a version pinned uvx run but passes an unpinned one

`uvx --from zyplux-cerberus==<old> cerberus` in a justfile or workflow is a
stale pin and fails; the unpinned `uvx --from zyplux-cerberus cerberus`
resolves the latest at run time and passes.

## 22.4 keeping container images at the latest tag

`ghcr.io/zyplux/<image>:<tag>` references in workflows and the justfile are
compared against the image's highest published version tag.

### 22.4.1 fails when a workflow pins an outdated ghcr image tag

A workflow `container:` line pinning a `ghcr.io/zyplux/` image below its
highest published version tag fails the check.

### 22.4.2 passes the floating latest tag

An image referenced as `:latest` always runs the newest release, so it is
never compared against the tag list.

## 22.5 degrading loudly when a registry is unreachable

Offline, rate-limited, or malformed registry responses must never turn into a
silent pass.

### 22.5.1 errors instead of passing when a registry lookup fails

When the lookup for a used artifact raises, the check emits an ERROR finding
naming the artifact and the failure, once per artifact, so the coverage gap
stays visible.
