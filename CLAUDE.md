# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Declarative, idempotent Ubuntu/Kubuntu Wayland laptop config: apt repos + packages, eGPU auto-PRIME at boot, and Chromium/Electron GPU flags. Same script handles first-run bootstrap and ongoing upkeep — re-runnable; cooks only rewrite files whose contents would actually change.

## Commands

- `just up` — run the full configuration (`./src/chef.py`); prompts for sudo at the start.
- `just lint` — `ruff check --fix` then `ruff format`.
- `just tc` — lint then `uvx pyright src` (depends on `lint`).
- Markdown lint: `rumdl` (configured in `.rumdl.toml`; disables `MD033`/`MD013`).
- Requires Python ≥3.14 (`pyproject.toml`). The only runtime deps are `loguru` and `toon-format`; everything else is stdlib.
- There is **no test suite** — verification is done by re-running `just up` and confirming "Unchanged:" lines for everything you didn't intend to touch.

## Architecture

### Orchestrator → cook contract

`src/chef.py` is the entry point. It does the following, in order:

1. Reads `src/recipe.toml`, builds a dependency graph from each top-level section's `depends_on`, and walks it in **topological order** via `graphlib.TopologicalSorter` (file order is the tiebreaker among ready nodes). It validates every section has a cook before doing any work.
2. If any section declares `needs_root = true`, primes sudo once up front (`sudo -v`), then for each section spawns its cook as a **subprocess** (not an import — the boundary is preserved for a later phase where chef imports cooks directly). `needs_root = true` → spawned under `sudo` with `--preserve-env`; `needs_root = false` → spawned directly. Chef refuses to run a non-root section if chef itself is root (toolchains would land under `/root`).
3. The section's TOML slice — minus the reserved `needs_root` / `depends_on` keys — is passed via the `SYS_CONF_PY_SECTION_JSON` env var.
4. Exit-code contract: `0` = success, `75` (`SOFT_FAIL_EXIT`) = soft fail (continue, name the section in a final stderr banner), anything else = hard fail (abort `just up`). `chef.py` itself exits 75 if any section soft-failed.

`configure_gpu` and `configure_apps` are ordinary graph nodes (declared `[configure_gpu]` / `[configure_apps]` with `depends_on = ["apt_pkg"]`); there is no `STANDALONE_PLAYBOOKS` list. Chef resolves a section `[foo]` to `src/foo_cook.py`, falling back to `src/foo.py` (the playbooks keep their plain names).

**Adding a new tool category** means adding a `[newcategory]` section to `recipe.toml` (with `needs_root` + `depends_on`) *and* creating `src/newcategory_cook.py` as a `CookBase` subclass. Missing cook → `chef.py` aborts with an error. **Prefer bash one-liners over Python:** if the operation fits the `[bash.<name>]` schema (idempotent shell snippets), add an entry there — no new Python file. A dedicated cook is for operations that genuinely need structured parsing, complex idempotency, or non-trivial state probing.

### Shared scaffolding (`src/harness.py`)

Every cook imports from here. Key utilities:

- `load_section()` — read the slice that `chef.py` passed via env. Sudo elevation is owned by chef now, so cooks no longer self-elevate; `load_section()` simply runs first in `main_for` so a missing-env or JSON error surfaces before any work.
- `start_log_tee()` — tees stdout/stderr into `logs/sys-conf-py-<timestamp>.log`. Honors `SYS_CONF_PY_LOG_FILE` if set (so all cooks in one run share one log file); pre-chowns log + dir to `SUDO_USER` so root-written lines keep the original owner.
- `stream_subprocess(cmd, ...)` — runs a child with merged stdout/stderr piped line-by-line through `loguru`. Forces `TERM=dumb` + `NO_COLOR=1` + `start_new_session=True` to strip ANSI and block `/dev/tty` bypass. Splits CR-overwrites into separate log lines. Use this, not `subprocess.run`, for anything whose output you want in the log.
- `write_if_changed(path, content, mode, note)` — the idempotency primitive: compare bytes, skip when equal, log `Unchanged:` vs `Writing  :`. Cooks should funnel **every** file write through this so re-runs stay quiet. `bash_cook` exposes it to shell snippets as a `write-if-changed` command on `$PATH`.
- `find_binary(name)` — `shutil.which` first, then `BOOTSTRAP_BIN_DIRS` (`~/.cargo/bin`, `~/.bun/bin`, `~/.local/bin`, `~/.claude/local`). Needed because `rustup` / `bun` / `uv` install into those dirs before they're on `PATH`. **Only call from non-root cooks** — `BOOTSTRAP_BIN_DIRS` was resolved against the invoking user's `$HOME` at import; a root cook's `Path.home()` would point at `/root`.
- `fetch_url(url)` — `urllib` with a custom `User-Agent: sys-conf-py` (some CDNs 403 the urllib default).

### Cook base class (`src/cook_base.py`)

Every cook subclasses `CookBase` and implements two synchronous methods:

- `install_or_update() -> Result` — does the work. Returns `Result(status, message, changed)` where `status` is `"ok" | "soft_fail" | "hard_fail"`; **expected** failures return a status rather than raising (only bugs propagate). Concurrency (thread pools, batch tools) is the cook's own business in this phase.
- `show_version() -> list[VersionInfo]` — read-only probe; always returns a list (loose contract for now, nothing branches on it).

`main_for(cls)` is the standard `__main__` entry point: it loads the section, enforces the privilege contract from the cook side (a `needs_root` cook refuses a non-root euid and vice-versa), tees the log, runs `install_or_update`, and maps `Result.status` onto the chef exit codes. `python src/<cook>.py --show-version` prints the probe as a TOON table for debugging.

### Cooks

Each cook owns one recipe section as a `CookBase` subclass. Behaviors that matter when editing:

- **`url_cook.py`** (`UrlCook`) — `[url.<name>]` entries; each is a `curl | bash` installer. Runs entries in parallel via `ThreadPoolExecutor`. Install failure → `hard_fail` (downstream may depend on the tool); update failure → `soft_fail` (tool stays usable). `needs_root = false`; refuses root — installers write into `$HOME`. `update_action` semantics: list → `<bin> <args...>`; `"rerun-installer"` → re-pipe URL; absent → no update. (This is the former `bash_cook.py`.)
- **`bash_cook.py`** (`BashCook`) — generic idempotent shell executor for `[bash.<name>]` entries. Runs each entry's `pre_update` / `install_or_update` / `post_update` snippets **sequentially in file order** via `stream_subprocess(["bash", "-c", …])`. `install_or_update` non-zero → `hard_fail`; pre/post non-zero → `soft_fail`. Puts a `write-if-changed` shim on `$PATH` (running under the cook's own interpreter so it imports `harness`) so heredoc'd file writes reuse the `write_if_changed` idempotency primitive. Idempotency is the snippet author's responsibility. Currently the home of apt's setup steps (prereqs, debconf, `trusted.gpg.d` hardening, Ubuntu pin), so `needs_root = true`.
- **`cargo_cook.py`** (`CargoCook`) — `[cargo].packages`; one batched `cargo binstall --no-confirm pkg1 pkg2 …` (binstall does its own parallel resolution + per-crate skip-if-current). Bootstraps `cargo-binstall` via a slow source compile if missing. Refuses root.
- **`uv_cook.py`** (`UvCook`) — `[uv].packages`; parallel `uv tool install` / `uv tool upgrade`, with the install/upgrade decision driven by a single up-front `uv tool list` parse. Refuses root.
- **`apt_repo_cook.py`** (`AptRepoCook`) — `[apt_repo.<name>]`, one subtable per third-party repo. Idempotent: GPG key under `/usr/share/keyrings/<name>.gpg` + `.sources` file with `Signed-By:` so each key authorises only its own repo. `needs_root = true`; `depends_on = ["bash"]` (needs the prereqs' gnupg).
- **`apt_pkg_cook.py`** (`AptPkgCook`) — `[apt_pkg].packages`. Drives `nala` (parallel downloads + `nala history undo`): `nala update`, a policy check, `full-upgrade`, `install`, `autoremove`. Fails fast before `full-upgrade` if any requested package has `apt-cache policy` priority 0 (not available in any configured repo). `needs_root = true`; `depends_on = ["bash", "apt_repo"]`.

Apt's cross-repo safety (Ubuntu pin → priority 900), the `trusted.gpg.d` `chattr +i` hardening, and the DPkg::Pre/Post-Invoke unlock hook now live as `[bash.<name>]` entries in `recipe.toml` (with their rationale preserved as comments) rather than Python — see the `[bash]` section there.

### Standalone playbooks

Declared in `recipe.toml` as `[configure_gpu]` / `[configure_apps]` (`needs_root = true`, `depends_on = ["apt_pkg"]`); chef dispatches them through the graph like any cook. Their internal logic is unchanged (not yet converted to the `CookBase` shape) — they read their own config and don't take a recipe slice.

- **`configure_gpu.py`** — installs `/usr/local/sbin/egpu-prime-switch` and `/etc/systemd/system/egpu-prime.service` (the service runs the switch before SDDM at boot). Also writes `/etc/modprobe.d/nvidia-power.conf` and adds `mem_sleep_default=deep` to `GRUB_CMDLINE_LINUX_DEFAULT` — both mitigate the s2idle / NVIDIA suspend crash documented in `docs/projects/sleep-crash/sleep-crash.md`. It does **not** write the eGPU-primary env file — that's owned by `egpu-prime-switch` (boot-time, because the device paths depend on the live card numbering; see `docs/projects/laptop-rendering-sluggishness/investigation.md`).
- **`configure_apps.py`** — reads `src/apps_config.toml`. Dispatches per app section on which marker key(s) are present: `desktop` (per-user `.desktop` override under `~/.local/share/applications/` with `env` prefix + `--<switch>`es + `--enable-features=`), `local_state` (Chromium-family `Local State` JSON merge for `brave://flags`-style UI mirroring — **skipped if the target browser is running** to avoid racing the write), `argv_json` (Electron-style allowlisted flag merge, e.g. VS Code), `settings_json` (merge an `env` block into a JSON settings file, e.g. `~/.claude/settings.json`). If any `.desktop` was rewritten, `kbuildsycoca6 --noincremental` runs as the invoking user — without it, KDE's launcher keeps spawning apps with the previously-cached `Exec` line.

### Static assets (`src/files/`)

Installed verbatim by `configure_gpu.py`:

- `egpu-prime-switch`, `egpu-prime.service` — the boot-time eGPU-primary selector + its systemd unit. `egpu-prime-switch` is a **standalone `/usr/bin/python3`, stdlib-only** script (no `harness`/`loguru`/uv imports — it runs as root before login, where none of that is importable). When the eGPU is on PCI it flips `boot_vga` onto it, writes `/etc/environment.d/10-egpu-primary.conf` (`KWIN_DRM_DEVICES` resolved to colon-free `/dev/dri/cardN` + `VULKAN_ADAPTER`), and selects `prime-select nvidia`; otherwise it removes that file and selects `on-demand`. A reboot drops the `boot_vga` bind-mount and the file is regenerated, so nothing goes stale.

(The former `ubuntu-archives.pref` and `99-trusted-gpgd-autounlock` are gone — their content is now inlined as heredocs in the `[bash.*]` entries of `recipe.toml`.)

## Editing conventions specific to this repo

- **All file writes go through `write_if_changed`** so idle re-runs print `Unchanged:` and exit fast. Don't introduce a plain `path.write_text(...)` — it breaks the "rerun is cheap" invariant. In `[bash.*]` snippets, pipe through the `write-if-changed` shim for the same reason.
- **All subprocesses that produce log-worthy output go through `stream_subprocess`** so they land in the tee'd log with consistent formatting; use `harness.run(...)` only for short utility calls whose stdout you'll capture programmatically.
- **`needs_root` and `depends_on` are declared in `recipe.toml`, not in code.** Chef owns sudo and ordering. Cooks no longer self-elevate — set `needs_root` on the section and the matching class attribute, and let `main_for` enforce the euid contract.
- **`find_binary` only from non-root (user) cooks** — `BOOTSTRAP_BIN_DIRS` binds to the invoking user's `$HOME` at import; a root cook's `Path.home()` is `/root`.
- **User-writable cooks refuse root** (`url_cook`, `cargo_cook`, `uv_cook`) via `needs_root = false` + the `CookBase` euid guard. If you add a new user-scope cook, set `needs_root = false` — toolchains landing under `/root` is a silent footgun.
- **Repo configuration is data, not code**: a new package goes in `recipe.toml`, a new flag in `apps_config.toml`, a new system-config one-off in a `[bash.<name>]` entry. The Python files should rarely change when adding/removing tools.

## Recovery

`docs/investigations/` contains write-ups of past failures (e.g. `sleep-crash.md` — the basis for the GRUB + modprobe NVIDIA tuning in `configure_gpu.py`). Logs live in `logs/sys-conf-py-<timestamp>.log`, one per `just up` run, chowned to the invoking user.
