# Unified install.toml — Plan

> **Status:** Phase 1 shape locked — readiness 95%
> **Last updated:** 2026-05-23
> **Walking skeleton:** one `install.toml` (draft at `plan/install.toml`) that replaces `url_config.toml`, `cargo_config.toml`, `uv_config.toml`, and `apt_config.toml`. Phase 1 is *just the TOML* — confirm shape, then plan the runner separately. `configure_apps` and `configure_gpu` stay as today.

## 1. Vision

Unify the four package-list configs (`apt`, `cargo`, `uv`, `bash`) into one declarative `install.toml`. **Phase 1** is the file shape itself — get the artifact right *first*. **Phase 2** (planned separately, after Phase 1 lands) is a runner that consumes it. `configure_apps` and `configure_gpu` are explicitly out of scope for v1 — they don't share the "package list" shape and would dilute the abstraction.

**Naming pattern:** every top-level section names the *installer tool* (`apt`, `cargo`, `uv`, `bash`). The thing being installed is identified inside the section — as a string in a `packages` array, or as a subtable header for items with extra fields (`[apt.repo.<name>]`, `[bash.<cli>]`).

## 2. Problem & motivation

Today's four package-list configs (`url_config.toml`, `cargo_config.toml`, `uv_config.toml`, `apt_config.toml`) live in separate files driving separate playbook scripts. Reasons to merge:

- One file to read to know what's on the box.
- Same shape for "this tool's package list" across apt/cargo/uv/url.
- Easier to add a new package manager later (one new section, same shape).
- Sets up — but does not yet implement — a future runner with one idempotency contract.

## 3. Users & primary scenarios

- **Primary user:** Sergiy, maintaining a personal Ubuntu workstation.
- **Key scenarios:**
  - "What does this machine have on it?" — open one file, see everything.
  - "Add a new tool" — pick the right section, add an entry, re-run `just up`.
  - "Move a package from one source to another" (e.g. apt → cargo) — delete one line, add another, no playbook switching.

## 4. Goals

- Single `install.toml` covering everything `url_config.toml` + `cargo_config.toml` + `uv_config.toml` + `apt_config.toml` cover today.
- Sections grouped by tool — `[apt]`, `[cargo]`, `[uv]`, `[[url_install]]`.
- All apt sub-config (`ubuntu_pin`, `repo`, `debconf`) nested under `[apt]` so apt-ness is structurally visible.
- Comments preserved verbatim from the originals where they document hidden constraints (e.g. nvidia-driver pinning, code-insiders debconf rationale).
- Zero loss of expressiveness — every field today's configs accept must still be expressible.

## 5. Non-goals (Phase 1 scope)

- **No runner yet.** Phase 1 ships the TOML; the runner is a separate downstream plan.
- **`configure_apps` and `configure_gpu` stay as today.** Their inputs (`apps_config.toml`, static files under `src/files/`) are not "package lists" and don't fit the unified shape.
- **No new managed items.** Strict 1:1 with what today's four configs declare.
- **No version-pin DSL beyond what apt already accepts.** `"name=version"` string format stays; cargo/uv don't get new pin syntax invented for them.

## 6. Constraints

- Python 3.14+ `tomllib` is the only parser — anything we write must round-trip cleanly through stdlib TOML.
- Comments are part of the deliverable — they encode incident learnings (nvidia branch pinning, Signal's `xenial` suite, the debconf rationale) and must survive the unify.
- Field-for-field expressive parity with today's configs — every optional field today's loaders accept (`args`, `keyring`, `source_path`, `architectures`, `components`, `update_action="rerun-installer"`, etc.) must still parse the same way.

## 7. Functional requirements

- [DECIDED] One file: `src/install.toml`.
- [DECIDED] `[apt]` table with `packages = [...]` (flat list of strings, version pins inline as `"name=version"`).
- [DECIDED] `[apt.ubuntu_pin]` table — same fields as today's top-level `[ubuntu_pin]`.
- [DECIDED] `[apt.repo.<name>]` named subtables — same fields as today's `[[repo]]`, minus the `name` field (subtable header IS the name). Dotted names quoted per TOML syntax: `[apt.repo."debian.griffo.io"]`.
- [DECIDED] `[apt.debconf.<handle>]` named subtables — same fields as today's `[[debconf]]`. The subtable handle is a synthetic identifier (package name is the default convenient choice).
- [DECIDED] `[cargo]` table with `packages = [...]`.
- [DECIDED] `[uv]` table with `packages = [...]`.
- [DECIDED] `[bash.<name>]` named subtables — same fields as today's `[[install]]`, minus the `name` field, and with `bin` defaulting to the subtable name when not set.
- [DECIDED] No forward-compat key reservations. Phase 2 introduces `depends_on` (and any other schema additions) when it needs them.

## 8. Walking skeleton (Phase 1)

The deliverable is exactly one file: `src/install.toml`. The current draft is at `plan/install.toml`. Once shape is locked:

1. Move `plan/install.toml` to `src/install.toml`.
2. Update each of the four existing playbooks (`install_from_urls.py`, `install_cargo_packages.py`, `install_uv_packages.py`, `configure_with_apt.py`) to read from the unified file, picking only its own section.
3. Delete the four old `*_config.toml` files.
4. Update `README.md` config table.
5. Verify `just up` converges identical state on a smoke-test machine.

No runner refactor yet — each playbook still owns its idempotency loop. The four scripts just point at one TOML instead of four.

## 9. Architecture sketch

Two layers, both narrow:

**Config layer.** A single TOML file with four top-level tool sections. Each section is the natural shape for its tool: bare-string `packages` lists for apt/cargo/uv (since pip/cargo/apt all key by name), and a richer `[[url_install]]` array for vendor URL installers because each needs URL, bin, args, update_action.

**Loader layer.** Each of the four existing playbooks gains a tiny shim: `tomllib.load(install.toml)["apt"]` (or `["cargo"]`, etc.) instead of `tomllib.load(apt_config.toml)`. No other code change.

`configure_apps.py` and `configure_gpu.py` keep reading their own files — they are explicitly outside this unification.

## 10. Tech stack

- **Python 3.14+ `tomllib`** for reading. [DECIDED]
- **No code changes to the harness primitives.** [DECIDED]
- **No new pyproject.toml dependencies.** [DECIDED]

## 11. Roadmap

- **Phase 1 (this plan):** unified `install.toml` shape locked; four playbooks repointed; old configs deleted. No behavior change.
- **Phase 2 (next plan):** runner refactor — centralize idempotency, add `--list`, add `depends_on`, parallel waves. This is where the "universal recipe runner like ansible" framing kicks in.
- **Phase 3:** maybe pull `configure_apps` and/or `configure_gpu` into the runner, once the recipe interface has been proven on the easier cases. Maybe `uninstall` and `show-latest`.

## 12. Decisions log

- **Narrowed scope to four package-list configs.** Rationale: `configure_apps` and `configure_gpu` have non-package-shaped state (JSON merges, .desktop rewrites, modprobe, GRUB) that doesn't share the "list + install/upgrade" interface, and including them in Phase 1 would force premature generalization of the runner abstraction.
- **Phase the rollout (TOML first, runner later).** Rationale: lets us validate the file shape without entangling it with runner-design decisions; matches the brief's "generate the unified install.toml first and confirm" guidance.
- **Per-type tables with group-friendly shorthand** as the overall shape (Interaction 3 option 2).
- **Named subtables for items with identifiers** (Interaction A option 2). `[apt.repo.<name>]`, `[apt.debconf.<handle>]`, `[command.<name>]`. Removes redundant `name = "..."` fields. Dotted repo names quoted in section headers per TOML.
- **Apt packages stay a flat list** (Interaction B option 3). Source-repo grouping remains comment-only; declarative grouping deferred to Phase 2 once `depends_on` exists.
- **Renamed `url_install` → `bash`** (Interaction C + Interaction D). The four section names now follow one rule: each names the installer tool. `apt` is the system package manager; `cargo`/`uv` are language tool managers; `bash` is what executes the fetched vendor scripts. `command` was the user's first pick but felt aspirational vs. the URL-pipe-only field set, so it was changed to `bash` — literal, parallel, doesn't overpromise.
- **No forward-compat reservations** (Interaction E option 2). Phase 1 ships exactly the shape it needs; Phase 2 grows the schema when it gets there.
- **Skipped Interactions 1 and 2** (resource-graph scope, sudo topology) — both are Phase 2 concerns, premature at Phase 1.

## 13. Open questions

1. The `bin` default for `[bash.<name>]` is now "the subtable name". Today the loader uses `block.get("bin", block["name"])` — `name` happens to match `bin` in every current entry, so the swap to "subtable key" is mechanical, but worth one-line confirming during the loader-swap PR.

## 14. Known unknowns

- Whether parsing the unified file through each playbook's existing loader is mechanically trivial (likely yes — same field names) or surfaces some hidden coupling (e.g. apt's `architectures` field default behavior).
- Whether moving from arrays to named subtables changes any iteration order the existing code relies on (apt repo install order, etc.). `tomllib` preserves insertion order in dicts, so likely safe, but worth a sanity check during the loader swap.
