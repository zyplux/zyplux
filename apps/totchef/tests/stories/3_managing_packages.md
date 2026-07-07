# 3. [Managing packages](test_3_managing_packages.py)

These cooks track what's installed and reconcile it against the recipe — apt and
snap by version (installing or upgrading only what differs), the `url` vendor cook
by presence. For each, the report shows the current and target state and whether the
resource was installed, upgraded, or left alone.

## 3.1 Install and upgrade apt packages

> As an operator, I want to declare a list of apt packages and have them installed
> and kept up to date, so that my system software matches my recipe.

### 3.1.1 apt pkg installed via nala full transaction

`[apt_pkg] packages = [...]` is installed/upgraded via **nala**, running a
full system transaction (`nala update`, `full-upgrade`, `install`, `autoremove`).

### 3.1.2 priority zero package fails fast with guidance

Before upgrading, totchef checks each package against `apt-cache policy` and
prints a verification table (installed/candidate version and pin priority and source
repo). If any package has **priority 0** (not found in any configured repo), the run
**fails fast** with guidance: check release-specific naming, confirm the component
(main/universe/multiverse/restricted) is enabled, or add the missing
`[apt_repo.<name>]`.

### 3.1.3 apt pkg runs as root after prereqs and repos

Runs as root; in the example recipe it depends on the apt prereqs and repos
being in place first.

### 3.1.4 reboot required notice survives to the end of the run

After the transaction, `[apt_pkg]` reads `/var/run/reboot-required` (and its
`.pkgs` companion naming the packages that caused it); when present, the
notice is carried as a delayed message into the `Action required` block.

## 3.2 Install and refresh snaps

> As an operator, I want to declare snap packages and have them installed and
> refreshed, so that snap apps are managed the same declarative way.

### 3.2.1 snap installs missing and refreshes installed

`[snap] packages = [...]` installs missing snaps and refreshes installed ones.

### 3.2.2 snap install failure hard refresh failure soft

An **install failure is hard** (the package the operator asked for isn't
there); a **refresh failure is soft** (the snap is still installed and usable, so
the run warns but continues).

### 3.2.3 missing snapd is a hard failure

If `snapd` isn't present, asking to install a snap is a hard failure with a
clear message.

## 3.3 Bootstrap vendor CLIs from their official installers

> As an operator, I want to install vendor tools from their `curl | bash` install
> scripts and keep them updated, so that tools like `bun`, `uv`, `rustup`, or
> `claude` are managed declaratively instead of by hand.

### 3.3.1 url fetches installer pipes to bash diffs presence

`[url.<name>]` fetches an installer URL and pipes it to `bash`, optionally with
`args`. Presence (not version) is what's diffed: if the binary is missing it's
installed; if present it's updated. Because version isn't tracked, a present tool
shows `would sync` in a plan and re-runs its `update_action` on every `up` — reported
as `unchanged` when the binary itself doesn't change.

### 3.3.2 binary name defaults to entry name overridable with bin

The binary name defaults to the entry name but can be overridden with `bin`.

### 3.3.3 update action arg list rerun installer or absent

Updating is controlled by `update_action`: a command arg list run against the
binary (e.g. `["self", "update"]`), the literal `"rerun-installer"` (re-pipe the
install script), or absent (leave as-is).

### 3.3.4 update guard runs before updating

An optional `update_guard` shell snippet runs before updating — e.g. stop a
running server and wait for it to quiesce before replacing its binary.

### 3.3.5 url install failure hard update failure soft

**Install failure is hard, update failure is soft** (the tool stays
installed).

### 3.3.6 version best effort parsed falls back to present

Version is best-effort parsed from `--version`; if it can't be parsed the cook
still works, reporting the tool as simply `present`.

### 3.3.7 url scheme defaults to https

A `url` without a scheme means https — `url = "bun.sh/install"` fetches
`https://bun.sh/install`. An explicit scheme passes through unchanged.

### 3.3.8 installers run from home so relative bindirs resolve

The installer is piped to `bash` with `$HOME` as its working directory. Vendor
scripts assume that — some default to a *relative* bin dir (chezmoi installs to
`.local/bin`), so running them from anywhere else drops the binary in the wrong
place. `$HOME` makes a relative bin dir resolve to `~/.local/bin`, exactly where
the cook's presence check (`find_binary`) looks.
