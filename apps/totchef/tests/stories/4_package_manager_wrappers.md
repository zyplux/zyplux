# 4. [Language package-manager wrappers](test_4_package_manager_wrappers.py)

These cooks wrap a language ecosystem's own package manager — `cargo` for Rust,
`uv` for Python, `bun` for global npm CLIs — installing tools into the invoking
user's home and keeping them current. Each needs its runtime present first (via the
matching `[url]` installer) and looks up latest versions from the ecosystem's
registry.

## 4.1 Install and update Rust crates

> As an operator, I want to declare Rust CLI crates and have them installed via
> prebuilt binaries, so that I get tools like `just` or `ripgrep` without a slow
> source compile each time.

### 4.1.1 cargo installs via binstall

`[cargo] packages = [...]` installs via `cargo binstall` (one batched command
that skips already-current crates itself).

### 4.1.2 cargo binstall is bootstrapped once if missing

If `cargo-binstall` is missing, totchef bootstraps it once via `cargo install`
(warning that this is a slow one-time source compile).

### 4.1.3 missing cargo fails hard pointing at url rustup

Requires `cargo` to exist first; if it's missing the run fails hard telling
the operator the `[url]` rustup install must run before `[cargo]` (typically via
`depends_on`).

### 4.1.4 latest crate versions looked up concurrently

Latest versions are looked up concurrently from crates.io for the plan.

### 4.1.5 latest version probes are time bounded

Every crates.io probe passes a timeout, so a stalled registry connection fails
fast to "unknown latest" rather than wedging the thread pool and hanging the
plan forever — the failure mode that left `just plan` stuck near 97%.

## 4.2 Install and upgrade Python CLI tools

> As an operator, I want to declare Python CLI tools and have each installed in its
> own isolated environment, so that tools like `ruff` don't collide with each
> other or my projects.

### 4.2.1 uv installs and upgrades each tool concurrently

`[uv] packages = [...]` installs/upgrades each tool via `uv tool install` /
`uv tool upgrade`, run **concurrently** behind uv's own locks.

### 4.2.2 uv failure reports hard naming the failed tools

If any tool fails, the run reports a hard failure naming the failed tools.

### 4.2.3 uv requires uv and looks up latest from pypi

Requires `uv` to be present (depends on the `[url]` uv installer); latest
versions are looked up concurrently from PyPI for the plan.

## 4.3 Install and upgrade global bun packages

> As an operator, I want to declare global npm CLI tools and have them installed
> and kept current with `bun`, so that tools like a coding agent are managed
> declaratively alongside my other packages.

### 4.3.1 bun installs and upgrades each global package

`[bun] packages = [...]` installs missing globals and upgrades drifted ones with a
single batched `bun add -g`; installed versions are read from bun's global tree.

### 4.3.2 bun requires bun and looks up latest from the npm registry

Requires `bun` to be present (depends on the `[url]` bun installer); if missing the
run fails hard pointing at the `[url]` bun install. Latest versions are looked up
concurrently from the npm registry for the plan.

### 4.3.3 bun installs globals into bun home not the cache dir

The cook pins `BUN_INSTALL` to bun's home directory before installing, so a global
binary lands in `~/.bun/bin` — on the user's PATH — rather than the
`$XDG_CACHE_HOME/.bun` location bun would otherwise pick once the run has dropped
privilege. Verified end-to-end in a container.

### 4.3.4 bun links node to its runtime so node shebang globals run

A node CLI's `#!/usr/bin/env node` shebang is left intact by `bun add -g`, so on a
bun-only machine the installed tool would fail with `env: 'node': No such file or
directory`. The cook drops a `node` symlink to bun in bun's bin dir, so the shebang
resolves and bun runs the CLI in node-compatibility mode. It is best-effort and
idempotent — it never clobbers a real `node`, and runs on every sync, so a
converged re-run with nothing to install still restores the runtime if it was removed.
