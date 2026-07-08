# 1. [Running totchef](test_1_running_totchef.py)

## 1.1 Apply a recipe to converge the system

> As an operator, I want to run `totchef up` and have my machine brought into
> compliance with my recipe, so that one command bootstraps a fresh install or
> reconciles drift on an existing one.

### 1.1.1 up resolves validates escalates previews then executes

`totchef up` resolves the recipe, loads and validates it, escalates to root,
previews the plan, and executes — creating or updating every resource that
differs from the desired state. Validation comes first, so an invalid recipe
is rejected with the schema error *before* the `sudo` prompt ever appears.

### 1.1.2 up is idempotent rerun reports nothing changed

The run is **idempotent**: re-running when nothing has drifted reports
"nothing changed" and makes no modifications. The work done on the second run is
only what genuinely differs. The one exception is the `url` vendor cook, which diffs
*presence* rather than version: a tool that is already present re-runs its
`update_action` on every run (see §3.3.1).

### 1.1.3 exit code communicates outcome

The exit code communicates the outcome to scripts and CI: `0` = success,
`75` = soft failure (something recoverable failed but the system is usable),
`1` = hard failure (a critical step failed and the apply was aborted).

### 1.1.4 invalid recipe rejects the run before any apply

Every run validates the recipe first — the same checks as `totchef lint`
([§10](10_recipe_linting_rules.md)) — and
one invalid entry rejects the whole run before any cook applies: even the
valid entries' targets stay untouched.

## 1.2 Preview changes without touching the system

> As an operator, I want to see exactly what `totchef` would change before it
> changes anything, so that I can review a risky run or check for drift safely.

### 1.2.1 plan dry run prints table makes no changes

`totchef plan` performs a **dry run**: it probes current state and prints a
plan table of every resource and what would happen (`would install`,
`would upgrade`, `would sync`, `would apply`, `up-to-date`, `ok`), but makes no
changes.

### 1.2.2 plan requires no root

A dry run requires **no root** — it never escalates privileges.

### 1.2.3 plan shows all resources including unchanged

The plan shows *all* resources (including unchanged ones) so the operator sees
the full intended end state, not just the diff.

### 1.2.4 up prints plan first from silent probe

During a real `up`, the same plan is printed first (from a silent probe pass)
so the operator sees what is about to happen before it happens.

*Validating a recipe without running it — `totchef lint` — is specified in
[10. Recipe linting rules](10_recipe_linting_rules.md).*

## 1.3 Find out which recipe will be used

> As an operator, I want to know which recipe totchef will pick up — and to pin one so it
> runs from anywhere — so that I'm never surprised by the wrong file being applied.

### 1.3.1 where prints resolved recipe path

`totchef where` prints the resolved recipe path and exits.

### 1.3.2 recipe discovery follows fixed precedence

Recipe discovery follows a fixed precedence: an explicit `--recipe`/`-r PATH` (a file or a
repo directory), then a recognized recipe filename (`totchef.toml`, `totchef_recipe.toml`,
or `totchef-recipe.toml`) found walking up from the current directory, then a recipe pinned
by `totchef init`.

### 1.3.3 no recipe found lists searched locations

When no recipe is found, the error lists every location that was searched, so
the operator knows exactly where to put one.

### 1.3.4 recipe flag accepts a directory

`--recipe DIR` accepts a repo directory, resolving to a recognized recipe filename inside
it — so the operator can point at a config/dotfiles repo without naming the file.

### 1.3.5 init pins a default recipe

`totchef init PATH` pins a recipe (a file, or a repo directory holding one) in the user
config (`~/.config/totchef/config.toml`), so a later `totchef up` with nothing nearer
resolves to it — letting `totchef up` run from anywhere.

### 1.3.6 init offers the discovered recipe

Run with no path, `totchef init` offers the recipe discovered in the current directory and
pins it once the operator confirms.

### 1.3.7 init pins a symlink as given

`totchef init PATH` pins a symlinked `PATH` as given rather than dereferencing it, so
repointing the symlink to a moved or renamed repo checkout carries the pin along without
rerunning `init`.

### 1.3.8 init errors when no recipe is found and none pinned

Run with no path, no recipe discoverable from the current directory, and nothing
pinned yet, `totchef init` rejects with a clear error instead of pinning nothing.

## 1.4 Discover available cooks

> As an operator, I want to list every configuration domain totchef can manage on
> this machine, so that I know which recipe sections are valid and where each comes
> from.

### 1.4.1 cooks lists section scope and origin

`totchef --list-cooks` prints a table of every resolvable cook: the **section**
name it serves (e.g. `apt_pkg`, `url`), its **scope** (`root` or `user`), and its
**origin** (`built-in`, `plugin:<dist>`, or `local:<path>`).

### 1.4.2 cooks reflects live registry

This reflects the live registry, so an installed plugin or a dropped-in local
cook shows up immediately.

## 1.5 Check the version

> As an operator, I want `totchef --version` to report the installed version, so I
> can confirm what I'm running.

### 1.5 version reports installed version

`totchef --version` prints the installed package version and exits.
