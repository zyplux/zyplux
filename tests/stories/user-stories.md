# totchef — User Stories

`totchef` is an idempotent, declarative system configurator for Ubuntu/Kubuntu,
shipped as a `uv` tool. You describe the machine you want in a `recipe.toml`; the
`totchef` command inspects the running system and makes it comply — installing and
upgrading packages, configuring apt repos, writing system and per-user files, and
tuning desktop apps. It is built for both first-run bootstrap of a fresh machine
and ongoing upkeep: every run only touches what would actually change.

These stories describe the software strictly from the **user's point of view** —
what someone running `totchef` (or authoring a recipe, or extending it) can do and
observe. They are derived from the behaviour implemented in `src/totchef/`.

The two roles referenced throughout:

- **Operator** — the person who owns a machine, writes its `recipe.toml`, and runs
  `totchef` to converge it.
- **Cook author** — a developer who extends `totchef` with a new domain (a "cook")
  via a plugin or a local file.

---

## 1. Running totchef

### 1.1 Apply a recipe to converge the system

> As an operator, I want to run `totchef up` and have my machine brought into
> compliance with my recipe, so that one command bootstraps a fresh install or
> reconciles drift on an existing one.

1.1.1 `totchef up` reads the recipe, validates it, escalates to root, previews the
plan, then executes — creating or updating every resource that differs from the
desired state.

1.1.2 The run is **idempotent**: re-running when nothing has drifted reports
"nothing changed" and makes no modifications. The work done on the second run is
only what genuinely differs.

1.1.3 The exit code communicates the outcome to scripts and CI: `0` = success,
`75` = soft failure (something recoverable failed but the system is usable),
`1` = hard failure (a critical step failed and the apply was aborted).

### 1.2 Preview changes without touching the system

> As an operator, I want to see exactly what `totchef` would change before it
> changes anything, so that I can review a risky run or check for drift safely.

1.2.1 `totchef plan` performs a **dry run**: it probes current state and prints a
plan table of every resource and what would happen (`would install`,
`would upgrade`, `would apply`, `up-to-date`, `ok`), but makes no changes.

1.2.2 A dry run requires **no root** — it never escalates privileges.

1.2.3 The plan shows *all* resources (including unchanged ones) so the operator sees
the full intended end state, not just the diff.

1.2.4 During a real `up`, the same plan is printed first (from a silent probe pass)
so the operator sees what is about to happen before it happens.

### 1.3 Validate a recipe without running it

> As an operator, I want to check that my recipe is well-formed before I rely on
> it, so that a typo fails fast instead of mid-run.

1.3.1 `totchef lint` validates the recipe against every cook's schema and the
dependency graph, then prints `<path>: valid` or exits with a precise error.

1.3.2 Validation catches: a section with no registered cook, an unknown or
misspelled recipe key (`extra='forbid'` rejects it rather than silently ignoring
it), a dependency naming a node that doesn't exist, a dependency cycle, a node that
depends on itself, and `needs_root` granted on a subtable header instead of a leaf
entry.

1.3.3 Linting needs no root and changes nothing.

### 1.4 Find out which recipe will be used

> As an operator, I want to know which `recipe.toml` totchef will pick up from my
> current directory, so that I'm never surprised by the wrong file being applied.

1.4.1 `totchef where` prints the resolved recipe path and exits.

1.4.2 Recipe discovery follows a fixed precedence: an explicit `--recipe`/`-r PATH`,
then the `$TOTCHEF_RECIPE` environment variable, then walking up from the current
directory looking for `recipe.toml` (project-local), then
`~/.config/totchef/recipe.toml`, then `/etc/totchef/recipe.toml`.

1.4.3 When no recipe is found, the error lists every location that was searched, so
the operator knows exactly where to put one.

### 1.5 Discover available cooks

> As an operator, I want to list every configuration domain totchef can manage on
> this machine, so that I know which recipe sections are valid and where each comes
> from.

1.5.1 `totchef cooks` prints a table of every resolvable cook: the **section** name
it serves (e.g. `apt_pkg`, `url`), its **scope** (`root` or `user`), and its
**origin** (`built-in`, `plugin:<dist>`, or `local:<path>`).

1.5.2 This reflects the live registry, so an installed plugin or a dropped-in local
cook shows up immediately.

### 1.6 Check the version

> As an operator, I want `totchef --version` to report the installed version, so I
> can confirm what I'm running.

---

## 2. Authoring a recipe

### 2.1 Declare the machine I want in one TOML file

> As an operator, I want the entire machine configuration expressed in a single
> declarative `recipe.toml`, so that the file is the single source of truth and a
> fresh clone reproduces the working state.

2.1.1 Each top-level section (`[apt_pkg]`, `[url.bun]`, `[file.grub_deep_sleep]`, …)
maps to a cook that manages that domain. A plain-data section is one unit of work; a
subtable section (`[url.<name>]`) fans out to one unit per entry.

2.1.2 The operator never writes imperative steps — only the desired end state. The
tool computes the diff and the order.

### 2.2 Express ordering between resources

> As an operator, I want to declare that one resource must be configured before
> another, so that, for example, apt repos exist before packages from them are
> installed.

2.2.1 Any entry can carry `depends_on = [...]`, naming another entry
(`bash.apt_prereqs`), a single-node section (`apt_pkg`), or a whole section
(`apt_repo`) which fans out to all of its entries.

2.2.2 totchef builds a dependency DAG and runs resources in topological order; a
node only starts once all of its dependencies have succeeded.

2.2.3 A dependency on a node that doesn't exist, or a cycle, or a self-dependency,
is caught at lint time with a message that explains how to fix it.

### 2.3 Set shared defaults across a section's entries

> As an operator, I want to set options once at the section level and have each
> entry inherit them, so that I don't repeat the same flags on every app.

2.3.1 A subtable section's own scalar/list keys become defaults folded into each
entry's slice. For lists (e.g. shared GPU `features`), the entry **extends** the
shared list; for everything else, the entry **overrides** the default.

2.3.2 Example: `[desktop]` declares a shared `features = [...]`, and
`[desktop.brave]` adds a couple more — Brave ends up with the union.

### 2.4 Grant root only where it's needed

> As an operator, I want privilege granted per resource at the finest grain, so
> that a user-scoped step never runs as root unnecessarily.

2.4.1 Whether a cook needs root is driven by the cook's own `needs_root` attribute,
but a recipe entry can also set `needs_root = true` to escalate a privilege-agnostic
cook (`bash`, `file`) for that one entry.

2.4.2 The lint **forbids** `needs_root` on a subtable section header, because that
would grant root to every entry wholesale — it must be set per leaf entry (least
privilege), and the error says so.

---

## 3. Managing packages (versioned domains)

These cooks track installed versions, compare them against requested/latest, and
install or upgrade only what differs. For each, the report shows the current and
target version and whether the resource was installed, upgraded, or left alone.

### 3.1 Install and upgrade apt packages

> As an operator, I want to declare a list of apt packages and have them installed
> and kept up to date, so that my system software matches my recipe.

3.1.1 `[apt_pkg] packages = [...]` is installed/upgraded via **nala**, running a
full system transaction (`nala update`, `full-upgrade`, `install`, `autoremove`).

3.1.2 Before upgrading, totchef checks each package against `apt-cache policy` and
prints a verification table (installed/candidate version and pin priority and source
repo). If any package has **priority 0** (not found in any configured repo), the run
**fails fast** with guidance: check release-specific naming, confirm the component
(main/universe/multiverse/restricted) is enabled, or add the missing
`[apt_repo.<name>]`.

3.1.3 Runs as root; in the example recipe it depends on the apt prereqs and repos
being in place first.

### 3.2 Install and refresh snaps

> As an operator, I want to declare snap packages and have them installed and
> refreshed, so that snap apps are managed the same declarative way.

3.2.1 `[snap] packages = [...]` installs missing snaps and refreshes installed ones.

3.2.2 An **install failure is hard** (the package the operator asked for isn't
there); a **refresh failure is soft** (the snap is still installed and usable, so
the run warns but continues).

3.2.3 If `snapd` isn't present, asking to install a snap is a hard failure with a
clear message.

### 3.3 Install and update Rust crates

> As an operator, I want to declare Rust CLI crates and have them installed via
> prebuilt binaries, so that I get tools like `just` or `ripgrep` without a slow
> source compile each time.

3.3.1 `[cargo] packages = [...]` installs via `cargo binstall` (one batched command
that skips already-current crates itself).

3.3.2 If `cargo-binstall` is missing, totchef bootstraps it once via `cargo install`
(warning that this is a slow one-time source compile).

3.3.3 Requires `cargo` to exist first; if it's missing the run fails hard telling
the operator the `[url]` rustup install must run before `[cargo]` (typically via
`depends_on`).

3.3.4 Latest versions are looked up concurrently from crates.io for the plan.

### 3.4 Install and upgrade Python CLI tools

> As an operator, I want to declare Python CLI tools and have each installed in its
> own isolated environment, so that tools like `ruff` don't collide with each
> other or my projects.

3.4.1 `[uv] packages = [...]` installs/upgrades each tool via `uv tool install` /
`uv tool upgrade`, run **concurrently** behind uv's own locks.

3.4.2 If any tool fails, the run reports a hard failure naming the failed tools.

3.4.3 Requires `uv` to be present (depends on the `[url]` uv installer); latest
versions are looked up concurrently from PyPI for the plan.

### 3.5 Bootstrap vendor CLIs from their official installers

> As an operator, I want to install vendor tools from their `curl | bash` install
> scripts and keep them updated, so that tools like `bun`, `uv`, `rustup`, or
> `claude` are managed declaratively instead of by hand.

3.5.1 `[url.<name>]` fetches an installer URL and pipes it to `bash`, optionally with
`args`. Presence (not version) is what's diffed: if the binary is missing it's
installed; if present it's updated.

3.5.2 The binary name defaults to the entry name but can be overridden with `bin`.

3.5.3 Updating is controlled by `update_action`: a command arg list run against the
binary (e.g. `["self", "update"]`), the literal `"rerun-installer"` (re-pipe the
install script), or absent (leave as-is).

3.5.4 An optional `update_guard` shell snippet runs before updating — e.g. stop a
running server and wait for it to quiesce before replacing its binary.

3.5.5 **Install failure is hard, update failure is soft** (the tool stays
installed).

3.5.6 Version is best-effort parsed from `--version`; if it can't be parsed the cook
still works, reporting the tool as simply `present`.

---

## 4. Configuring system state (root domains)

### 4.1 Add third-party apt repositories securely

> As an operator, I want to declare a third-party apt repo with its signing key and
> have it configured the modern signed-by way, so that I can install vendor
> packages without insecure global keyrings.

4.1.1 `[apt_repo.<name>]` fetches the repo's GPG key (de-armoring an ASCII-armored
key automatically), writes it to `/usr/share/keyrings/<name>.gpg`, and writes a
deb822 `.sources` file under `/etc/apt/sources.list.d/` with a `Signed-By:` pointing
at that keyring.

4.1.2 The operator declares `key_url` and `uris`, with optional `suites`,
`components`, `architectures`, and custom `keyring`/`source_path`.

4.1.3 `suites` may contain `{release}`, which is substituted with the detected
Ubuntu release codename — so the same recipe works across releases.

4.1.4 The repo is considered configured only when **both** the keyring and the
`.sources` file exist; otherwise it's re-applied.

### 4.2 Install files with exact content

> As an operator, I want to install a file with exact bytes — either inline content
> or a bundled asset — and have a follow-up action fire only when it actually
> changes, so that I can manage `/etc` drop-ins, systemd units, and scripts
> declaratively.

4.2.1 `[file.<name>]` writes a file to `path` from either inline `content` or a
`source` asset bundled with totchef (under `totchef/files/`), with a given `mode`.
Exactly one of `content`/`source` must be set.

4.2.2 The file is diffed by content hash, so it's only rewritten when the bytes
differ.

4.2.3 A `post_hook` runs **only when the file changed** — e.g. `update-grub` after a
GRUB drop-in, or `systemctl daemon-reload` after a unit. This makes expensive
refresh actions fire exactly when needed and never on a no-op run.

4.2.4 Privilege-agnostic: set `needs_root = true` per entry for files under `/etc`,
`/usr`, etc.

### 4.3 Run arbitrary idempotent shell steps

> As an operator, I want an escape hatch to run a shell command idempotently — with
> a check that decides whether it's even needed — so that I can handle the
> long tail of system tweaks no dedicated cook covers.

4.3.1 `[bash.<name>]` declares an `apply` command, plus an optional `current_state`
command and a `desired_state` string. totchef runs the `current_state` probe; if its
output already equals `desired_state`, the step is skipped; otherwise `apply` runs.

4.3.2 With no `current_state`, the step is treated as "no check" and always applies.

4.3.3 Used in the example recipe for things like apt pinning, debconf preseeding,
and installing apt prerequisites — each guarded by a cheap state probe so re-runs are
no-ops.

4.3.4 Privilege-agnostic: grant root per entry.

---

## 5. Tuning desktop applications (per-user domains)

These cooks edit per-user files in the operator's home directory (resolved to the
invoking user even though the apply runs under sudo). They're typically used to
push GPU acceleration flags into browsers and Electron apps.

### 5.1 Override an app's desktop launcher

> As an operator, I want to inject environment variables, switches, and feature
> flags into an app's launcher, so that the app always starts with my GPU/Wayland
> tuning when launched from the menu.

5.1.1 `[desktop.<app>]` reads a system `.desktop` file, rewrites its `Exec=` line to
add an `env` prefix, `--switch`es, and `--enable-features=...`, and writes the result
to `~/.local/share/applications/` (a per-user override).

5.1.2 The rewrite is **idempotent and deduplicating**: re-applying doesn't stack
duplicate flags, changing a switch's value replaces it, and new args are inserted
before trailing field codes (`%U`, `%F`, …).

5.1.3 On change, it refreshes KDE's `ksycoca` (tolerant of non-KDE systems) so the
launcher stops spawning the app with the stale command, and reminds the operator to
restart the app.

5.1.4 If the source `.desktop` doesn't exist yet, it reports that the package must be
installed first (rather than failing the whole run).

### 5.2 Inject flags into Chromium and Electron apps

> As an operator, I want to enable Chromium feature flags (and Electron `argv.json`
> options) for browsers and Electron-based editors, so that hardware video
> acceleration and Wayland support are turned on per app.

5.2.1 `[chromium_flags.<app>]` edits one of two targets (exactly one must be set):

5.2.1.1 `local_state` — a Chromium `Local State` JSON, merging `local_state_flags`
into `browser.enabled_labs_experiments`.

5.2.1.2 `argv_json` — an Electron `argv.json`, merging an `argv` table and
`--enable-features` from a `features` list (tolerating `//` comments in the existing
file).

5.2.2 Diffed by rendered-JSON hash, so it only writes when flags actually change.

5.2.3 For `Local State`, it **won't write while the browser is running** (a guard
via `pgrep` skips the entry to avoid racing the browser's own writes), naming the
process via `process_name` if it differs from the entry name.

5.2.4 If the base file doesn't exist yet, it tells the operator to launch the app
once and re-run; invalid JSON is left untouched and soft-fails.

5.2.5 On change it reminds the operator to restart the app.

### 5.3 Merge environment settings into a JSON config

> As an operator, I want to merge a block of environment values into the `env` key
> of an app's JSON settings file while preserving everything else, so that I can
> set tool config (e.g. Claude Code settings) declaratively without clobbering the
> file.

5.3.1 `[settings.<app>]` merges `settings_env` into the `env` object of a JSON file
under the operator's home, keeping all other keys intact.

5.3.2 Diffed by merged-JSON hash; invalid JSON is left as-is and soft-fails rather
than corrupting the file.

---

## 6. Safety, correctness, and trust

### 6.1 Trust that re-runs only change what drifted

> As an operator, I want every run to be safe to repeat, so that I can run totchef
> on a schedule or whenever I'm unsure, without fear of redundant or destructive
> work.

6.1.1 Every cook **probes** current state and acts only on the difference. Versioned
cooks skip up-to-date packages; state cooks skip resources whose content hash already
matches.

6.1.2 `post_hook`s fire only on actual change, so expensive refreshes don't run on
no-op passes.

### 6.2 Understand that totchef creates and updates but never prunes

> As an operator, I want to know that removing a section from my recipe leaves the
> existing artifact in place, so that I'm not surprised by what teardown does (and
> doesn't) happen.

6.2.1 Convergence is **create/update only**. Dropping an entry from the recipe (or
uninstalling its target) leaves prior artifacts — a written `/etc` drop-in, a repo's
keyring + `.sources`, a `.desktop` override — in place. Teardown is manual and
deliberate.

### 6.3 Escalate to root only for the apply, and drop privilege otherwise

> As an operator, I want totchef to request root only when applying, and to run
> each user-scoped step as me rather than as root, so that the privilege surface is
> minimal and files land with the right ownership.

6.3.1 `totchef up` re-execs itself under `sudo`, pinning the already-resolved recipe
path and shared log file across the boundary so root sees the same file.

6.3.2 Each resource runs in a forked child: a `needs_root` child keeps root; every
other child **drops privilege** back to the invoking user (gid → groups → uid) and
repoints `HOME`/`USER`/`PATH`. So user files are written as the user, and freshly
bootstrapped toolchains (`~/.cargo/bin`, `~/.bun/bin`, `~/.local/bin`) are found on
the next step's PATH.

6.3.3 `plan` and `lint` never escalate.

### 6.4 Distinguish recoverable failures from fatal ones

> As an operator, I want failures classified by severity, so that a cosmetic
> hiccup doesn't abort my whole run but a real problem does.

6.4.1 **Hard failure** aborts the apply and exits `1` (e.g. a requested package
isn't available anywhere, a `bash apply` command errors, a `uv` tool install fails).

6.4.2 **Soft failure** warns, finishes the run, and exits `75` (e.g. a snap
*refresh* failed, a `post_hook` failed, a target file held invalid JSON).

6.4.3 The end-of-run report names which cooks hard- or soft-failed.

### 6.5 Skip steps that shouldn't run right now

> As an operator, I want a guard that can skip a step when a precondition isn't met,
> so that, for example, a browser config isn't rewritten while the browser is
> running.

6.5.1 State-cook entries support a `pre_hook` guard: a non-zero exit **skips** the
item (reported as `skipped`, not failed) — a benign skip, not an error.

6.5.2 Cooks compose their own intrinsic guards with the operator's `pre_hook` (e.g.
the Chromium cook chains a "browser not running" check with any recipe-declared
guard).

6.5.3 `pre_hook`/`post_hook` are only valid on state-cook sections; declaring one on
a versioned section fails the lint instead of silently never running.

---

## 7. Observing a run

### 7.1 See a clear, color-coded report of what happened

> As an operator, I want a readable summary table at the end of a run, so that I can
> tell at a glance what was installed, upgraded, applied, or left alone.

7.1.1 The report is a table with `cook-node`, `current`, `latest`, and `action`
columns. On an interactive terminal it's a rich table with color-coded actions
(green for installed/upgraded/applied, yellow for "would …", red for failures, dim
for unchanged); on a non-terminal it's plain TOON text.

7.1.2 A real `up` shows only changed/failed rows plus a footer counting unchanged
resources and total elapsed time; a `plan` shows every row.

7.1.3 Content-hash diffs are humanized — a matching hash reads `present`, a drifting
one reads `stale`.

### 7.2 Watch progress while a long run executes

> As an operator, I want live feedback during a run, so that I know it's working and
> roughly how far along it is.

7.2.1 On an interactive terminal, a transient progress bar shows completed/total
resources and elapsed time; it's cleared on exit, leaving the logs above it.

7.2.2 Each cook's log lines are colorized and tagged with the cook's name in a stable
per-cook color, so the interleaved output of concurrently-running cooks stays
readable.

7.2.3 Start lines announce who is running (and, for user nodes, what they're waiting
on and what they unblock); completion lines report timing and which downstream
resources just unlocked.

### 7.3 Keep a timestamped log of every run

> As an operator, I want each run recorded to a log file owned by me, so that I can
> audit or debug after the fact, even though the apply ran as root.

7.3.1 Each run writes a timestamped log under the invoking user's state dir
(`~/.local/state/totchef/logs/`), resolved from `SUDO_USER` so a root re-exec still
logs to the user's home, then chowned back to the user.

7.3.2 All output — the parent's and every forked cook's stdout/stderr — funnels
through a single pump so log lines never interleave with the live table/progress
region.

7.3.3 A dry run shows only the plan table on the terminal while still recording every
line to the log file.

---

## 8. Extending totchef (cook authors)

### 8.1 Add a new configuration domain as a plugin

> As a cook author, I want to add a new recipe section backed by my own cook, so
> that totchef can manage a domain it doesn't ship with.

8.1.1 A cook is a `CookBase` subclass registered under the `totchef.cooks`
entry-point group; the section name it serves is the entry-point name. Built-in and
third-party cooks register the same way, and `totchef cooks` shows the origin.

### 8.2 Prototype a cook without packaging it

> As a cook author, I want to drop a single Python file into my config dir and have
> totchef pick it up, so that I can prototype a domain without building a package.

8.2.1 A loose `~/.config/totchef/cooks/<section>_cook.py` (containing exactly one
`CookBase` subclass; the `_cook`/`_root_cook` suffix is stripped to derive the
section) is loaded as a local cook and **shadows** a built-in of the same name — an
escape hatch for overriding or prototyping.

### 8.3 Choose the right cook shape for my domain

> As a cook author, I want base classes that match common patterns, so that I only
> implement the domain-specific probe/act logic and inherit diffing, scheduling,
> and reporting.

8.3.1 **VersionedCook** for versioned packages: implement
`list_requested`/`list_installed`/`find_latest`/`sync`. `PackageListCook` covers
plain `packages = [...]` sections.

8.3.2 **StateCook** for desired-state resources: implement
`get_current_state`/`get_desired_state`/`apply_resource` (+ hooks). `FileStateCook`
already diffs by sha256 of rendered bytes vs the on-disk file — a subclass just
supplies the target path and the rendered content.

8.3.3 The cook only *probes* and *acts*; the orchestrator owns every diff and
idempotency decision, so a cook holds no diff logic.

### 8.4 Get a typo'd recipe rejected against my schema

> As a cook author, I want each cook to define a strict schema for its recipe
> entries, so that an operator's typo fails the lint instead of being silently
> ignored.

8.4.1 A cook declares an `entry_model` (a pydantic model with `extra='forbid'`).
`totchef lint` validates each node's recipe slice against it and reports every
violation as a precise `[node] location: message` line.
