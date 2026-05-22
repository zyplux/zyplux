# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

| Command | What it does |
|---|---|
| `just up` | Full system setup. Spawns each playbook in order via `src/main.py`. The only user-facing entry point. |
| `just lint` | `ruff check --fix && ruff format`. |
| `just tc` | Runs `lint` then `uvx pyright src`. |

There are no tests in this repo.

## Architecture

**Single entry point.** `just up` runs `./src/main.py`, which sets `SYS_CONF_PY_LOG_FILE`, primes sudo, then spawns each playbook via `subprocess.run([sys.executable, playbook])`. Order (defined in `PLAYBOOKS` in `main.py`):

1. `install_from_urls.py` — vendor `curl | bash` CLIs from `url_config.toml` (runs as user)
2. `install_cargo_packages.py` — `cargo_config.toml`; bootstraps cargo-binstall on fresh systems via `cargo install`, then self-hosts via the same TOML (user)
3. `install_uv_packages.py` — `uv_config.toml` (user)
4. `configure_with_apt.py` — `apt_config.toml` (re-execs under sudo)
5. `configure_gpu.py` — egpu-prime systemd service (re-execs under sudo)
6. `configure_apps.py` — `apps_config.toml` (re-execs under sudo)

**Why subprocesses, not imports.** Each root-requiring playbook calls `reexec_under_sudo(SCRIPT)` which runs `os.execvp("sudo", [..., sys.executable, str(script), ...])`. `execvp` *replaces* the calling process. If `main.py` imported and called the playbook functions, the orchestrator would be gone after the first sudo step. Subprocesses isolate the execvp to each child.

**Shared log file via env var.** `SYS_CONF_PY_LOG_FILE` is set once in `main.py` (`os.environ.setdefault`), then propagates through every spawned subprocess and *across the sudo boundary* via `sudo --preserve-env=SYS_CONF_PY_LOG_FILE` in `reexec_under_sudo`. Each playbook calls `start_log_tee()` which `tee -a`s into that file. One `just up` run = one consolidated log under `logs/`, chowned to `SUDO_USER`.

**Subprocess output → loguru.** Use `stream_subprocess(cmd, ...)` from `harness.py` for any external command whose output you want logged. It runs with `TERM=dumb`, `NO_COLOR=1`, and `start_new_session=True`, captures merged stdout/stderr, splits CR-overwrites into separate frames, and routes each line through `logger.info`. `start_new_session=True` is what blocks nala from bypassing the pipe by opening `/dev/tty`. Don't reach for raw `subprocess.run` for streamable work — only for short capture-output calls (e.g. `gpg --dearmor`).

**Idempotency by file diff.** `write_if_changed(path, content)` in `harness.py` only writes when bytes differ; logs `Unchanged: <path>` on no-op. Re-running `just up` is cheap by design — every system-file write should go through this.

**User vs root playbooks.** Scripts that refuse root (`sys.exit(...)` when `os.geteuid() == 0`) install per-user tools — cargo/uv/bun lands in `$HOME` and would land in `/root` if run as root. Scripts that *require* root call `reexec_under_sudo(SCRIPT)` at the top of `main()`. Don't mix the two roles in one playbook.

**Vendor installer dispatch (`url_config.toml`).** Each `[[install]]` block: if `bin` is missing, fetch `url` and pipe into bash with optional `args`; if present, dispatch on `update_action` — a list runs `<bin> <update_action...>`, the literal string `"rerun-installer"` re-fetches and re-pipes. Absent `update_action` means leave as-is.

## Conventions

- **Python 3.14+** (`requires-python = ">=3.14"` in `pyproject.toml`). Stdlib `tomllib` for TOML, match statements, etc. — no `tomli` or other backports.
- **Dependencies in `pyproject.toml`**, project venv at `.venv`, uv-managed. Playbook scripts have **no PEP 723 inline metadata** and **no shebang** — they're spawned by `main.py`, never run directly. `main.py` is the only file with `+x` and a shebang (`#!/usr/bin/env -S uv run`).
- **Pyright config in `pyproject.toml`** under `[tool.pyright]` with `venvPath = "."` / `venv = ".venv"`. Required so `uvx pyright src` (run from an ephemeral uvx env) finds project deps.
- **`from harness import ...`** works in playbooks because Python adds the script's directory (`src/`) to `sys.path[0]` on direct execution; `main.py` and the playbooks all live in `src/` and share the same import resolution.
- **Static assets live in `src/files/`** — copied verbatim by playbooks. Edit those files directly rather than embedding their content in Python strings.

## Adding a new playbook

1. Create `src/<name>.py` with **no shebang, no `+x` bit, no PEP 723 block**.
2. Import from `harness`: typically `SRC_DIR`, `start_log_tee`, `stream_subprocess`, `write_if_changed`, and `reexec_under_sudo` if root is needed.
3. In `main()`: if root-required, `reexec_under_sudo(SCRIPT)` first. If user-only, `sys.exit(...)` early when `os.geteuid() == 0`. Then `start_log_tee()`.
4. If config-driven, read `src/<name>_config.toml` via `tomllib`. Add a row to the config table in `README.md`.
5. Append the filename to `PLAYBOOKS` in `src/main.py` in the position that respects the user/root ordering (user-scoped first, root-requiring last).
