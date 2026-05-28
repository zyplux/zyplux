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

### 1.1 [Apply a recipe to converge the system](test_1_running_totchef.py)

> As an operator, I want to run `totchef up` and have my machine brought into
> compliance with my recipe, so that one command bootstraps a fresh install or
> reconciles drift on an existing one.

#### 1.1.1 up resolves escalates validates previews then executes

`totchef up` resolves the recipe, escalates to root, then loads and validates
it, previews the plan, and executes — creating or updating every resource that
differs from the desired state. Escalation comes first, so even an invalid recipe
triggers the `sudo` prompt *before* the validation error surfaces.

#### 1.1.2 up is idempotent rerun reports nothing changed

The run is **idempotent**: re-running when nothing has drifted reports
"nothing changed" and makes no modifications. The work done on the second run is
only what genuinely differs. The one exception is the `url` vendor cook, which diffs
*presence* rather than version: a tool that is already present re-runs its
`update_action` on every run (see §3.3.1).

#### 1.1.3 exit code communicates outcome

The exit code communicates the outcome to scripts and CI: `0` = success,
`75` = soft failure (something recoverable failed but the system is usable),
`1` = hard failure (a critical step failed and the apply was aborted).

### 1.2 [Preview changes without touching the system](test_1_running_totchef.py)

> As an operator, I want to see exactly what `totchef` would change before it
> changes anything, so that I can review a risky run or check for drift safely.

#### 1.2.1 plan dry run prints table makes no changes

`totchef plan` performs a **dry run**: it probes current state and prints a
plan table of every resource and what would happen (`would install`,
`would upgrade`, `would sync`, `would apply`, `up-to-date`, `ok`), but makes no
changes.

#### 1.2.2 plan requires no root

A dry run requires **no root** — it never escalates privileges.

#### 1.2.3 plan shows all resources including unchanged

The plan shows *all* resources (including unchanged ones) so the operator sees
the full intended end state, not just the diff.

#### 1.2.4 up prints plan first from silent probe

During a real `up`, the same plan is printed first (from a silent probe pass)
so the operator sees what is about to happen before it happens.

### 1.3 [Validate a recipe without running it](test_1_running_totchef.py)

> As an operator, I want to check that my recipe is well-formed before I rely on
> it, so that a typo fails fast instead of mid-run.

#### 1.3.1 lint validates and prints path valid

`totchef lint` validates the recipe against every cook's schema and the
dependency graph, then prints `<path>: valid` or exits with a precise error.

#### 1.3.2 lint catches schema and graph errors

Validation catches: a section with no registered cook, an unknown or
misspelled recipe key (`extra='forbid'` rejects it rather than silently ignoring
it), a dependency naming a node that doesn't exist, a dependency cycle, a node that
depends on itself, and `needs_root` granted on a subtable header instead of a leaf
entry.

#### 1.3.3 lint needs no root and changes nothing

Linting needs no root and changes nothing.

### 1.4 [Find out which recipe will be used](test_1_running_totchef.py)

> As an operator, I want to know which `recipe.toml` totchef will pick up from my
> current directory, so that I'm never surprised by the wrong file being applied.

#### 1.4.1 where prints resolved recipe path

`totchef where` prints the resolved recipe path and exits.

#### 1.4.2 recipe discovery follows fixed precedence

Recipe discovery follows a fixed precedence: an explicit `--recipe`/`-r PATH`,
then the `$TOTCHEF_RECIPE` environment variable, then walking up from the current
directory looking for `recipe.toml` (project-local), then
`~/.config/totchef/recipe.toml`, then `/etc/totchef/recipe.toml`.

#### 1.4.3 no recipe found lists searched locations

When no recipe is found, the error lists every location that was searched, so
the operator knows exactly where to put one.

### 1.5 [Discover available cooks](test_1_running_totchef.py)

> As an operator, I want to list every configuration domain totchef can manage on
> this machine, so that I know which recipe sections are valid and where each comes
> from.

#### 1.5.1 cooks lists section scope and origin

`totchef --list-cooks` prints a table of every resolvable cook: the **section**
name it serves (e.g. `apt_pkg`, `url`), its **scope** (`root` or `user`), and its
**origin** (`built-in`, `plugin:<dist>`, or `local:<path>`).

#### 1.5.2 cooks reflects live registry

This reflects the live registry, so an installed plugin or a dropped-in local
cook shows up immediately.

### 1.6 [Check the version](test_1_running_totchef.py)

> As an operator, I want `totchef --version` to report the installed version, so I
> can confirm what I'm running.

#### 1.6 version reports installed version

`totchef --version` prints the installed package version and exits.

---

## 2. Authoring a recipe

### 2.1 [Declare the machine I want in one TOML file](test_2_authoring_a_recipe.py)

> As an operator, I want the entire machine configuration expressed in a single
> declarative `recipe.toml`, so that the file is the single source of truth and a
> fresh clone reproduces the working state.

#### 2.1.1 each section maps to a cook plain vs subtable

Each top-level section (`[apt_pkg]`, `[url.bun]`, `[file.grub_deep_sleep]`, …)
maps to a cook that manages that domain. A plain-data section is one unit of work; a
subtable section (`[url.<name>]`) fans out to one unit per entry.

#### 2.1.2 operator declares desired state not steps

The operator never writes imperative steps — only the desired end state. The
tool computes the diff and the order.

### 2.2 [Express ordering between resources](test_2_authoring_a_recipe.py)

> As an operator, I want to declare that one resource must be configured before
> another, so that, for example, apt repos exist before packages from them are
> installed.

#### 2.2.1 depends on names entry node or section

Any entry can carry `depends_on = [...]`, naming another entry
(`bash.apt_prereqs`), a single-node section (`apt_pkg`), or a whole section
(`apt_repo`) which fans out to all of its entries.

#### 2.2.2 resources run in topological order

totchef builds a dependency DAG and runs resources in topological order; a
node only starts once all of its dependencies have succeeded.

#### 2.2.3 bad dependency is caught at lint

A dependency on a node that doesn't exist, or a cycle, or a self-dependency,
is caught at lint time with a message that explains how to fix it.

### 2.3 [Set shared defaults across a section's entries](test_2_authoring_a_recipe.py)

> As an operator, I want to set options once at the section level and have each
> entry inherit them, so that I don't repeat the same flags on every app.

#### 2.3.1 section defaults fold into entries lists extend others override

A subtable section's own scalar/list keys become defaults folded into each
entry's slice. For lists (e.g. shared GPU `features`), the entry **extends** the
shared list; for everything else, the entry **overrides** the default.

#### 2.3.2 shared desktop features yield union per entry

Example: `[desktop]` declares a shared `features = [...]`, and
`[desktop.brave]` adds a couple more — Brave ends up with the union.

### 2.4 [Grant root only where it's needed](test_2_authoring_a_recipe.py)

> As an operator, I want privilege granted per resource at the finest grain, so
> that a user-scoped step never runs as root unnecessarily.

#### 2.4.1 needs root per entry escalates a privilege agnostic cook

Whether a cook needs root is driven by the cook's own `needs_root` attribute,
but a recipe entry can also set `needs_root = true` to escalate a privilege-agnostic
cook (`bash`, `file`) for that one entry.

#### 2.4.2 lint forbids needs root on a subtable header

The lint **forbids** `needs_root` on a subtable section header, because that
would grant root to every entry wholesale — it must be set per leaf entry (least
privilege), and the error says so.

---

## 3. Managing packages

These cooks track what's installed and reconcile it against the recipe — apt and
snap by version (installing or upgrading only what differs), the `url` vendor cook
by presence. For each, the report shows the current and target state and whether the
resource was installed, upgraded, or left alone.

### 3.1 [Install and upgrade apt packages](test_3_managing_packages.py)

> As an operator, I want to declare a list of apt packages and have them installed
> and kept up to date, so that my system software matches my recipe.

#### 3.1.1 apt pkg installed via nala full transaction

`[apt_pkg] packages = [...]` is installed/upgraded via **nala**, running a
full system transaction (`nala update`, `full-upgrade`, `install`, `autoremove`).

#### 3.1.2 priority zero package fails fast with guidance

Before upgrading, totchef checks each package against `apt-cache policy` and
prints a verification table (installed/candidate version and pin priority and source
repo). If any package has **priority 0** (not found in any configured repo), the run
**fails fast** with guidance: check release-specific naming, confirm the component
(main/universe/multiverse/restricted) is enabled, or add the missing
`[apt_repo.<name>]`.

#### 3.1.3 apt pkg runs as root after prereqs and repos

Runs as root; in the example recipe it depends on the apt prereqs and repos
being in place first.

### 3.2 [Install and refresh snaps](test_3_managing_packages.py)

> As an operator, I want to declare snap packages and have them installed and
> refreshed, so that snap apps are managed the same declarative way.

#### 3.2.1 snap installs missing and refreshes installed

`[snap] packages = [...]` installs missing snaps and refreshes installed ones.

#### 3.2.2 snap install failure hard refresh failure soft

An **install failure is hard** (the package the operator asked for isn't
there); a **refresh failure is soft** (the snap is still installed and usable, so
the run warns but continues).

#### 3.2.3 missing snapd is a hard failure

If `snapd` isn't present, asking to install a snap is a hard failure with a
clear message.

### 3.3 [Bootstrap vendor CLIs from their official installers](test_3_managing_packages.py)

> As an operator, I want to install vendor tools from their `curl | bash` install
> scripts and keep them updated, so that tools like `bun`, `uv`, `rustup`, or
> `claude` are managed declaratively instead of by hand.

#### 3.3.1 url fetches installer pipes to bash diffs presence

`[url.<name>]` fetches an installer URL and pipes it to `bash`, optionally with
`args`. Presence (not version) is what's diffed: if the binary is missing it's
installed; if present it's updated. Because version isn't tracked, a present tool
shows `would sync` in a plan and re-runs its `update_action` on every `up` — reported
as `unchanged` when the binary itself doesn't change.

#### 3.3.2 binary name defaults to entry name overridable with bin

The binary name defaults to the entry name but can be overridden with `bin`.

#### 3.3.3 update action arg list rerun installer or absent

Updating is controlled by `update_action`: a command arg list run against the
binary (e.g. `["self", "update"]`), the literal `"rerun-installer"` (re-pipe the
install script), or absent (leave as-is).

#### 3.3.4 update guard runs before updating

An optional `update_guard` shell snippet runs before updating — e.g. stop a
running server and wait for it to quiesce before replacing its binary.

#### 3.3.5 url install failure hard update failure soft

**Install failure is hard, update failure is soft** (the tool stays
installed).

#### 3.3.6 version best effort parsed falls back to present

Version is best-effort parsed from `--version`; if it can't be parsed the cook
still works, reporting the tool as simply `present`.

---

## 4. Language package-manager wrappers

These cooks wrap a language ecosystem's own package manager — `cargo` for Rust,
`uv` for Python, `bun` for global npm CLIs — installing tools into the invoking
user's home and keeping them current. Each needs its runtime present first (via the
matching `[url]` installer) and looks up latest versions from the ecosystem's
registry.

### 4.1 [Install and update Rust crates](test_4_package_manager_wrappers.py)

> As an operator, I want to declare Rust CLI crates and have them installed via
> prebuilt binaries, so that I get tools like `just` or `ripgrep` without a slow
> source compile each time.

#### 4.1.1 cargo installs via binstall

`[cargo] packages = [...]` installs via `cargo binstall` (one batched command
that skips already-current crates itself).

#### 4.1.2 cargo binstall is bootstrapped once if missing

If `cargo-binstall` is missing, totchef bootstraps it once via `cargo install`
(warning that this is a slow one-time source compile).

#### 4.1.3 missing cargo fails hard pointing at url rustup

Requires `cargo` to exist first; if it's missing the run fails hard telling
the operator the `[url]` rustup install must run before `[cargo]` (typically via
`depends_on`).

#### 4.1.4 latest crate versions looked up concurrently

Latest versions are looked up concurrently from crates.io for the plan.

### 4.2 [Install and upgrade Python CLI tools](test_4_package_manager_wrappers.py)

> As an operator, I want to declare Python CLI tools and have each installed in its
> own isolated environment, so that tools like `ruff` don't collide with each
> other or my projects.

#### 4.2.1 uv installs and upgrades each tool concurrently

`[uv] packages = [...]` installs/upgrades each tool via `uv tool install` /
`uv tool upgrade`, run **concurrently** behind uv's own locks.

#### 4.2.2 uv failure reports hard naming the failed tools

If any tool fails, the run reports a hard failure naming the failed tools.

#### 4.2.3 uv requires uv and looks up latest from pypi

Requires `uv` to be present (depends on the `[url]` uv installer); latest
versions are looked up concurrently from PyPI for the plan.

### 4.3 [Install and upgrade global bun packages](test_4_package_manager_wrappers.py)

> As an operator, I want to declare global npm CLI tools and have them installed
> and kept current with `bun`, so that tools like a coding agent are managed
> declaratively alongside my other packages.

#### 4.3.1 bun installs and upgrades each global package

`[bun] packages = [...]` installs missing globals and upgrades drifted ones with a
single batched `bun add -g`; installed versions are read from bun's global tree.

#### 4.3.2 bun requires bun and looks up latest from the npm registry

Requires `bun` to be present (depends on the `[url]` bun installer); if missing the
run fails hard pointing at the `[url]` bun install. Latest versions are looked up
concurrently from the npm registry for the plan.

#### 4.3.3 bun installs globals into bun home not the cache dir

The cook pins `BUN_INSTALL` to bun's home directory before installing, so a global
binary lands in `~/.bun/bin` — on the user's PATH — rather than the
`$XDG_CACHE_HOME/.bun` location bun would otherwise pick once the run has dropped
privilege. Verified end-to-end in a container.

#### 4.3.4 bun links node to its runtime so node shebang globals run

A node CLI's `#!/usr/bin/env node` shebang is left intact by `bun add -g`, so on a
bun-only machine the installed tool would fail with `env: 'node': No such file or
directory`. The cook drops a `node` symlink to bun in bun's bin dir, so the shebang
resolves and bun runs the CLI in node-compatibility mode. It is best-effort and
idempotent — it never clobbers a real `node`, and runs on every sync, so a
converged re-run with nothing to install still restores the runtime if it was removed.

---

## 5. Configuring system state (root domains)

### 5.1 [Add third-party apt repositories securely](test_5_configuring_system_state.py)

> As an operator, I want to declare a third-party apt repo with its signing key and
> have it configured the modern signed-by way, so that I can install vendor
> packages without insecure global keyrings.

#### 5.1.1 apt repo fetches key dearmors writes keyring and sources

`[apt_repo.<name>]` fetches the repo's GPG key (de-armoring an ASCII-armored
key automatically), writes it to `/usr/share/keyrings/<name>.gpg`, and writes a
deb822 `.sources` file under `/etc/apt/sources.list.d/` with a `Signed-By:` pointing
at that keyring.

#### 5.1.2 operator declares key url uris and optional fields

The operator declares `key_url` and `uris`, with optional `suites`,
`components`, `architectures`, and custom `keyring`/`source_path`.

#### 5.1.3 suites release placeholder substituted with codename

`suites` may contain `{release}`, which is substituted with the detected
Ubuntu release codename — so the same recipe works across releases.

#### 5.1.4 repo configured only when keyring and sources both exist

The repo is considered configured only when **both** the keyring and the
`.sources` file exist; otherwise it's re-applied.

### 5.2 [Install files with exact content](test_5_configuring_system_state.py)

> As an operator, I want to install a file with exact bytes — either inline content
> or a bundled asset — and have a follow-up action fire only when it actually
> changes, so that I can manage `/etc` drop-ins, systemd units, and scripts
> declaratively.

#### 5.2.1 file writes from content or bundled source with mode

`[file.<name>]` writes a file to `path` from either inline `content` or a
`source` asset bundled with totchef (under `totchef/files/`), with a given `mode`.
Exactly one of `content`/`source` must be set.

#### 5.2.2 file diffed by content hash

The file is diffed by content hash, so it's only rewritten when the bytes
differ.

#### 5.2.3 post hook runs only when the file changed

A `post_hook` runs **only when the file changed** — e.g. `update-grub` after a
GRUB drop-in, or `systemctl daemon-reload` after a unit. This makes expensive
refresh actions fire exactly when needed and never on a no-op run.

#### 5.2.4 file is privilege agnostic root per entry

Privilege-agnostic: set `needs_root = true` per entry for files under `/etc`,
`/usr`, etc.

### 5.3 [Run arbitrary idempotent shell steps](test_5_configuring_system_state.py)

> As an operator, I want an escape hatch to run a shell command idempotently — with
> a check that decides whether it's even needed — so that I can handle the
> long tail of system tweaks no dedicated cook covers.

#### 5.3.1 bash skips apply when current state equals desired

`[bash.<name>]` declares an `apply` command, plus an optional `current_state`
command and a `desired_state` string. totchef runs the `current_state` probe; if its
output already equals `desired_state`, the step is skipped; otherwise `apply` runs.

#### 5.3.2 bash with no current state always applies

With no `current_state`, the step is treated as "no check" and always applies.

#### 5.3.3 bash guarded steps are no ops on rerun

Used in the example recipe for things like apt pinning, debconf preseeding,
and installing apt prerequisites — each guarded by a cheap state probe so re-runs are
no-ops.

#### 5.3.4 bash is privilege agnostic root per entry

Privilege-agnostic: grant root per entry.

---

## 6. Tuning desktop applications (per-user domains)

These cooks edit per-user files in the operator's home directory (resolved to the
invoking user even though the apply runs under sudo). They're typically used to
push GPU acceleration flags into browsers and Electron apps.

### 6.1 [Override an app's desktop launcher](test_6_tuning_desktop_applications.py)

> As an operator, I want to inject environment variables, switches, and feature
> flags into an app's launcher, so that the app always starts with my GPU/Wayland
> tuning when launched from the menu.

#### 6.1.1 desktop rewrites exec line into a user override

`[desktop.<app>]` reads a system `.desktop` file, rewrites its `Exec=` line to
add an `env` prefix, `--switch`es, and `--enable-features=...`, and writes the result
to `~/.local/share/applications/` (a per-user override).

#### 6.1.2 desktop rewrite is idempotent and deduplicating

The rewrite is **idempotent and deduplicating**: re-applying doesn't stack
duplicate flags, changing a switch's value replaces it, and new args are inserted
before trailing field codes (`%U`, `%F`, …).

#### 6.1.3 desktop on change refreshes ksycoca and reminds restart

On change, it refreshes KDE's `ksycoca` (tolerant of non-KDE systems) so the
launcher stops spawning the app with the stale command, and reminds the operator to
restart the app.

#### 6.1.4 desktop missing source reports install package first

If the source `.desktop` doesn't exist yet, it reports that the package must be
installed first (rather than failing the whole run).

### 6.2 [Inject flags into Chromium and Electron apps](test_6_tuning_desktop_applications.py)

> As an operator, I want to enable Chromium feature flags (and Electron `argv.json`
> options) for browsers and Electron-based editors, so that hardware video
> acceleration and Wayland support are turned on per app.

`[chromium_flags.<app>]` edits one of two targets (exactly one must be set):

#### 6.2.1.1 local state merges into enabled labs experiments

`local_state` — a Chromium `Local State` JSON, merging `local_state_flags`
into `browser.enabled_labs_experiments`.

#### 6.2.1.2 argv json merges argv and enable features tolerating comments

`argv_json` — an Electron `argv.json`, merging an `argv` table and
`--enable-features` from a `features` list (tolerating `//` comments in the existing
file).

#### 6.2.2 chromium flags diffed by rendered json hash

Diffed by rendered-JSON hash, so it only writes when flags actually change.

#### 6.2.3 local state skipped while browser running

For `Local State`, it **won't write while the browser is running** (a guard
via `pgrep` skips the entry to avoid racing the browser's own writes), naming the
process via `process_name` if it differs from the entry name.

#### 6.2.4 missing base file advises launch once invalid json soft fails

If the base file doesn't exist yet, it tells the operator to launch the app
once and re-run; invalid JSON is left untouched and soft-fails.

#### 6.2.5 chromium flags on change reminds restart

On change it reminds the operator to restart the app.

### 6.3 [Merge environment settings into a JSON config](test_6_tuning_desktop_applications.py)

> As an operator, I want to merge a block of environment values into the `env` key
> of an app's JSON settings file while preserving everything else, so that I can
> set tool config (e.g. Claude Code settings) declaratively without clobbering the
> file.

#### 6.3.1 settings merges settings env into env preserving other keys

`[settings.<app>]` merges `settings_env` into the `env` object of a JSON file
under the operator's home, keeping all other keys intact.

#### 6.3.2 settings diffed by merged json hash invalid json soft fails

Diffed by merged-JSON hash; invalid JSON is left as-is and soft-fails rather
than corrupting the file.

---

## 7. Safety, correctness, and trust

### 7.1 [Trust that re-runs only change what drifted](test_7_safety_correctness_and_trust.py)

> As an operator, I want every run to be safe to repeat, so that I can run totchef
> on a schedule or whenever I'm unsure, without fear of redundant or destructive
> work.

#### 7.1.1 cooks probe and act only on the difference

Every cook **probes** current state and acts only on the difference. Versioned
cooks skip up-to-date packages; state cooks skip resources whose content hash already
matches. The `url` cook is the exception: it diffs presence, not version, so a present
tool re-runs its `update_action` each run rather than being skipped (§3.3.1).

#### 7.1.2 post hooks fire only on actual change

`post_hook`s fire only on actual change, so expensive refreshes don't run on
no-op passes.

### 7.2 [Understand that totchef creates and updates but never prunes](test_7_safety_correctness_and_trust.py)

> As an operator, I want to know that removing a section from my recipe leaves the
> existing artifact in place, so that I'm not surprised by what teardown does (and
> doesn't) happen.

#### 7.2.1 convergence is create update only never prunes

Convergence is **create/update only**. Dropping an entry from the recipe (or
uninstalling its target) leaves prior artifacts — a written `/etc` drop-in, a repo's
keyring + `.sources`, a `.desktop` override — in place. Teardown is manual and
deliberate.

### 7.3 [Escalate to root only for the apply, and drop privilege otherwise](test_7_safety_correctness_and_trust.py)

> As an operator, I want totchef to request root only when applying, and to run
> each user-scoped step as me rather than as root, so that the privilege surface is
> minimal and files land with the right ownership.

#### 7.3.1 up re execs under sudo pinning recipe and log

`totchef up` re-execs itself under `sudo`, pinning the already-resolved recipe
path and shared log file across the boundary so root sees the same file.

#### 7.3.2 forked child drops privilege for user nodes

Each resource runs in a forked child: a `needs_root` child keeps root; every
other child **drops privilege** back to the invoking user (gid → groups → uid) and
repoints `HOME`/`USER`/`PATH`. So user files are written as the user, and freshly
bootstrapped toolchains (`~/.cargo/bin`, `~/.bun/bin`, `~/.local/bin`) are found on
the next step's PATH.

#### 7.3.3 plan and lint never escalate

`plan` and `lint` never escalate.

### 7.4 [Distinguish recoverable failures from fatal ones](test_7_safety_correctness_and_trust.py)

> As an operator, I want failures classified by severity, so that a cosmetic
> hiccup doesn't abort my whole run but a real problem does.

#### 7.4.1 hard failure aborts the apply and exits 1

**Hard failure** aborts the apply and exits `1` (e.g. a requested package
isn't available anywhere, a `bash apply` command errors, a `uv` tool install fails).

#### 7.4.2 soft failure warns finishes and exits 75

**Soft failure** warns, finishes the run, and exits `75` (e.g. a snap
*refresh* failed, a `post_hook` failed, a target file held invalid JSON).

#### 7.4.3 report names which cooks hard or soft failed

The end-of-run report names which cooks hard- or soft-failed.

### 7.5 [Skip steps that shouldn't run right now](test_7_safety_correctness_and_trust.py)

> As an operator, I want a guard that can skip a step when a precondition isn't met,
> so that, for example, a browser config isn't rewritten while the browser is
> running.

#### 7.5.1 pre hook nonzero exit skips the item

State-cook entries support a `pre_hook` guard: a non-zero exit **skips** the
item (reported as `skipped`, not failed) — a benign skip, not an error.

#### 7.5.2 cooks compose intrinsic guards with pre hook

Cooks compose their own intrinsic guards with the operator's `pre_hook` (e.g.
the Chromium cook chains a "browser not running" check with any recipe-declared
guard).

#### 7.5.3 hooks run on versioned sections too

`pre_hook`/`post_hook` are valid on every cook section, versioned ones included.
On a versioned section (`[cargo]`, `[bun]`, …) the `pre_hook` gates the whole
sync — a non-zero exit **skips** it — and the `post_hook` fires once after a
change (e.g. linking a freshly-installed binary onto `PATH`).

---

## 8. Observing a run

### 8.1 [See a clear, color-coded report of what happened](test_8_observing_a_run.py)

> As an operator, I want a readable summary table at the end of a run, so that I can
> tell at a glance what was installed, upgraded, applied, or left alone.

#### 8.1.1 report table color coded on terminal plain toon otherwise

The report is a table with `cook-node`, `before`, `current`, `latest`, and
`action` columns. `before` is the state snapshot from before the cook acted;
`current` is the state right now (post-sync on `up`, equal to `before` on
`plan` since no action has happened); `latest` is the upgrade target. On an
interactive terminal it's a rich table with color-coded actions (green for
installed/upgraded/applied, yellow for "would …", red for failures, dim for
unchanged); on a non-terminal it's plain TOON text.

#### 8.1.2 up shows changed rows plus footer plan shows all

A real `up` shows only changed/failed rows plus a footer counting unchanged
resources and total elapsed time; a `plan` shows every row.

#### 8.1.3 content hash diffs humanized present or stale

Content-hash diffs are humanized — a matching hash reads `present`, a drifting
one reads `stale`.

#### 8.1.4 before and current diverge on upgrade

After an `up` that upgrades a resource, the `before` cell shows the pre-sync
version and the `current` cell shows the post-sync version, so the row reads
as a real diff (e.g. `url.claude,2.1.152,2.1.153,—,upgraded`). `current` is a
fresh post-sync probe — not a copy of `before` — so the column reflects what
is installed right now.

#### 8.1.5 failed install keeps before equal current

When an install errors, the row reads `before == current ≠ latest` — both
sides show `(none)` because nothing landed, while `latest` shows the unmet
target. The operator can see at a glance that the requested version did not
arrive.

### 8.2 [Watch progress while a long run executes](test_8_observing_a_run.py)

> As an operator, I want live feedback during a run, so that I know it's working and
> roughly how far along it is.

#### 8.2.1 transient progress bar cleared on exit

On an interactive terminal, a transient progress bar shows completed/total
resources and elapsed time; it's cleared on exit, leaving the logs above it.

#### 8.2.2 log lines colorized and tagged per cook

Each cook's log lines are colorized and tagged with the cook's name in a stable
per-cook color, so the interleaved output of concurrently-running cooks stays
readable.

#### 8.2.3 start and completion lines announce waits and unblocks

Start lines announce who is running (and, for user nodes, what they're waiting
on and what they unblock); completion lines report timing and which downstream
resources just unlocked.

### 8.3 [Keep a timestamped log of every run](test_8_observing_a_run.py)

> As an operator, I want each run recorded to a log file owned by me, so that I can
> audit or debug after the fact, even though the apply ran as root.

#### 8.3.1 timestamped log under user state dir chowned back

Each run writes a timestamped log under the invoking user's state dir
(`~/.local/state/totchef/logs/`), resolved from `SUDO_USER` so a root re-exec still
logs to the user's home, then chowned back to the user.

#### 8.3.2 all output funnels through a single pump

All output — the parent's and every forked cook's stdout/stderr — funnels
through a single pump so log lines never interleave with the live table/progress
region.

#### 8.3.3 dry run shows only plan on terminal but logs everything

A dry run shows only the plan table on the terminal while still recording every
line to the log file.

---

## 9. Extending totchef (cook authors)

### 9.1 [Add a new configuration domain as a plugin](test_9_extending_totchef.py)

> As a cook author, I want to add a new recipe section backed by my own cook, so
> that totchef can manage a domain it doesn't ship with.

#### 9.1.1 cook registered under entry point group serves its section

A cook is a `CookBase` subclass registered under the `totchef.cooks`
entry-point group; the section name it serves is the entry-point name. Built-in and
third-party cooks register the same way, and `totchef cooks` shows the origin.

### 9.2 [Prototype a cook without packaging it](test_9_extending_totchef.py)

> As a cook author, I want to drop a single Python file into my config dir and have
> totchef pick it up, so that I can prototype a domain without building a package.

#### 9.2.1 local cook file is picked up and shadows a builtin

A loose `~/.config/totchef/cooks/<section>_cook.py` (containing exactly one
`CookBase` subclass; the `_cook`/`_root_cook` suffix is stripped to derive the
section) is loaded as a local cook and **shadows** a built-in of the same name — an
escape hatch for overriding or prototyping.

### 9.3 [Choose the right cook shape for my domain](test_9_extending_totchef.py)

> As a cook author, I want base classes that match common patterns, so that I only
> implement the domain-specific probe/act logic and inherit diffing, scheduling,
> and reporting.

#### 9.3.1 versioned cook implements requested installed latest sync

**VersionedCook** for versioned packages: implement
`list_requested`/`list_installed`/`find_latest`/`sync`. `PackageListCook` covers
plain `packages = [...]` sections.

#### 9.3.2 state cook implements current desired apply filestate diffs

**StateCook** for desired-state resources: implement
`get_current_state`/`get_desired_state`/`apply_resource` (+ hooks). `FileStateCook`
already diffs by sha256 of rendered bytes vs the on-disk file — a subclass just
supplies the target path and the rendered content.

#### 9.3.3 cook only probes and acts orchestrator owns the diff

The cook only *probes* and *acts*; the orchestrator owns every diff and
idempotency decision, so a cook holds no diff logic.

### 9.4 [Get a typo'd recipe rejected against my schema](test_9_extending_totchef.py)

> As a cook author, I want each cook to define a strict schema for its recipe
> entries, so that an operator's typo fails the lint instead of being silently
> ignored.

#### 9.4.1 cook entry model lints recipe slice reporting violations

A cook declares an `entry_model` (a pydantic model with `extra='forbid'`).
`totchef lint` validates each node's recipe slice against it and reports every
violation as a precise `[node] location: message` line.
