# 6. [Tuning desktop applications (per-user domains)](test_6_tuning_desktop_applications.py)

These cooks edit per-user files in the operator's home directory (resolved to the
invoking user even though the apply runs under sudo). They're typically used to
push GPU acceleration flags into browsers and Electron apps.

## 6.1 Override an app's desktop launcher

> As an operator, I want to inject environment variables, switches, and feature
> flags into an app's launcher, so that the app always starts with my GPU/Wayland
> tuning when launched from the menu.

### 6.1.1 desktop rewrites exec line into a user override

`[desktop.<app>]` reads a system `.desktop` file, rewrites its `Exec=` line to
add an `env` prefix, `--switch`es, and `--enable-features=...`, and writes the result
to `~/.local/share/applications/` (a per-user override).

### 6.1.2 desktop rewrite is idempotent and deduplicating

The rewrite is **idempotent and deduplicating**: re-applying doesn't stack
duplicate flags, changing a switch's value replaces it, and new args are inserted
before trailing field codes (`%U`, `%F`, …).

### 6.1.3 desktop on change refreshes ksycoca and reminds restart

On change, it refreshes KDE's `ksycoca` (tolerant of non-KDE systems) so the
launcher stops spawning the app with the stale command, and reminds the operator to
restart the app.

### 6.1.4 desktop missing source reports install package first

If the source `.desktop` doesn't exist yet, it reports that the package must be
installed first (rather than failing the whole run).

## 6.2 Inject flags into Chromium and Electron apps

> As an operator, I want to enable Chromium feature flags (and Electron `argv.json`
> options) for browsers and Electron-based editors, so that hardware video
> acceleration and Wayland support are turned on per app.

`[chromium_flags.<app>]` edits one of two targets (exactly one must be set):

### 6.2.1.1 local state merges into enabled labs experiments

`local_state` — a Chromium `Local State` JSON, merging `local_state_flags`
into `browser.enabled_labs_experiments`.

### 6.2.1.2 argv json merges argv and enable features tolerating comments

`argv_json` — an Electron `argv.json`, merging an `argv` table and
`--enable-features` from a `features` list (tolerating `//` comments in the existing
file).

### 6.2.2 chromium flags diffed by rendered json hash

Diffed by rendered-JSON hash, so it only writes when flags actually change.

### 6.2.3 local state skipped while browser running

For `Local State`, it **won't write while the browser is running** (a guard
via `pgrep` skips the entry to avoid racing the browser's own writes), naming the
process via `process_name` if it differs from the entry name.

### 6.2.4 missing base file advises launch once invalid json soft fails

If the base file doesn't exist yet, it tells the operator to launch the app
once and re-run; invalid JSON is left untouched and soft-fails.

### 6.2.5 chromium flags on change reminds restart

On change it reminds the operator to restart the app.

## 6.3 Merge environment settings into a JSON config

> As an operator, I want to merge a block of environment values into the `env` key
> of an app's JSON settings file while preserving everything else, so that I can
> set tool config (e.g. Claude Code settings) declaratively without clobbering the
> file.

### 6.3.1 settings merges settings env into env preserving other keys

`[settings.<app>]` merges `settings_env` into the `env` object of a JSON file
under the operator's home, keeping all other keys intact.

### 6.3.2 settings diffed by merged json hash invalid json soft fails

Diffed by merged-JSON hash; invalid JSON is left as-is and soft-fails rather
than corrupting the file.
