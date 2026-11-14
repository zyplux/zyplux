# 4. [Language package-manager wrappers](test_4_package_manager_wrappers.py)

These cooks wrap a language ecosystem's own package manager — `cargo` for Rust,
`uv` for Python, `pnpm` for global npm CLIs — installing tools into the invoking
user's home and keeping them current. Each needs its runtime present first (via the
matching `[url]` installer). Cargo and uv look up latest versions from their
ecosystem registries; pnpm applies its own version-eligibility policy.

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

## 4.3 Install and upgrade global pnpm packages

> As an operator, I want to declare global npm CLI tools and have them installed
> and kept current with `pnpm`, so that tools like a coding agent are managed
> declaratively alongside my other packages.

### 4.3.1 pnpm installs and upgrades each global package

`[pnpm] packages = [...]` installs missing globals and upgrades drifted ones with a
single batched `pnpm add -g`; installed versions are read from pnpm's global tree.

### 4.3.2 pnpm requires pnpm

Requires `pnpm` to be present (depends on the `[url]` pnpm installer); if missing the
run fails hard pointing at the `[url]` pnpm install.

### 4.3.3 pnpm installs globals into pnpm home not an inherited data dir

Left to itself pnpm roots its global tree at `$XDG_DATA_HOME/pnpm`, so a variable
inherited from the pre-drop environment would strand globals outside the operator's
home. The cook pins `PNPM_HOME` and puts its bin dir on PATH before any global
command, so the tree lands in `~/.local/share/pnpm` — where the operator's shell
finds it. Verified end-to-end in a container.

### 4.3.4 pnpm keeps a global within its declared major

A versioned package specifier such as `node@26` reports under the package's name and refreshes through the declared range on every run, so the latest Node 26 release is installed without drifting into a later major.

### 4.3.5 pnpm rejects conflicting specs for one package

Two specifiers that identify the same package are ambiguous, so `[pnpm]` rejects declarations such as `node@26` alongside `node@27` instead of silently choosing one.

### 4.3.6 pnpm delegates release-age resolution

Every declared global is reconciled through `pnpm add -g`, so pnpm selects the newest version eligible under the active `minimumReleaseAge` policy instead of TotChef bypassing that policy with the registry's raw `latest` tag.
