# 5. [Configuring system state (root domains)](test_5_configuring_system_state.py)

## 5.1 Add third-party apt repositories securely

> As an operator, I want to declare a third-party apt repo with its signing key and
> have it configured the modern signed-by way, so that I can install vendor
> packages without insecure global keyrings.

### 5.1.1 apt repo fetches key dearmors writes keyring and sources

`[apt_repo.<name>]` fetches the repo's GPG key (de-armoring an ASCII-armored
key automatically), writes it to `/usr/share/keyrings/<name>.gpg`, and writes a
deb822 `.sources` file under `/etc/apt/sources.list.d/` with a `Signed-By:` pointing
at that keyring.

### 5.1.2 operator declares key url uris and optional fields

The operator declares `key_url`, with optional `url`, `uris`, `suites`,
`components`, `architectures`, and custom `keyring`/`source_path`.

### 5.1.3 suites release placeholder substituted with codename

`suites` may contain `{release}`, which is substituted with the detected
Ubuntu release codename — so the same recipe works across releases.

### 5.1.4 repo configured only when keyring and sources both exist

The repo is considered configured only when **both** the keyring and the
`.sources` file exist; otherwise it's re-applied.

### 5.1.5 relative urls resolve against the repo url

`url` is the repo's base, with the scheme optional (https assumed):
`key_url`/`uris` without a scheme resolve against it, and an omitted `uris`
defaults to the base itself. Absolute URLs keep working unchanged, and a
relative URL without `url` is rejected at lint. The keyring/`.sources` files
keep the entry's name, so the entry stays a short alias (`signal-desktop`)
while `url` carries the host.

```toml
[apt_repo.signal-desktop]
url = "updates.signal.org/desktop/apt"
key_url = "keys.asc"
suites = "xenial"
```

### 5.1.6 pin priority writes origin pin into preferences

`pin_priority` writes `/etc/apt/preferences.d/<name>.pref` pinning the repo's
origin host (derived from `uris`) to that priority, so a package the repo ships
can outrank the Ubuntu-archive pin (`[bash.ubuntu_pin]`, priority 900) instead
of apt silently keeping the older universe build. The repo counts as configured
only once that pref file also exists, alongside the keyring and `.sources`.

```toml
[apt_repo.github-cli]
url = "cli.github.com/packages"
key_url = "githubcli-archive-keyring.gpg"
pin_priority = 1001
```

## 5.2 Install files with exact content

> As an operator, I want to install a file with exact bytes — either inline content
> or a bundled asset — and have a follow-up action fire only when it actually
> changes, so that I can manage `/etc` drop-ins, systemd units, and scripts
> declaratively.

### 5.2.1 file writes from content or bundled source with mode

`[file.<name>]` writes a file to `path` from either inline `content` or a
`source` asset beside the recipe (in `totchef_files/`), with a given `mode`.
Setting both is rejected.

### 5.2.2 file diffed by content hash

The file is diffed by content hash, so it's only rewritten when the bytes
differ.

### 5.2.3 post hook runs only when the file changed

A `post_hook` runs **only when the file changed** — e.g. `update-grub` after a
GRUB drop-in, or `systemctl daemon-reload` after a unit. This makes expensive
refresh actions fire exactly when needed and never on a no-op run.

### 5.2.4 file path expands tilde for per user installs

A `~` in `path` resolves against `$HOME`, so per-user entries (e.g.
`~/.local/bin` tools) stay portable across machines and users.

### 5.2.5 file is privilege agnostic root per entry

Privilege-agnostic: set `needs_root = true` per entry for files under `/etc`,
`/usr`, etc.

### 5.2.6 source defaults to the bundled file named after the entry

With neither `content` nor `source` set, the entry installs the unique bundled
file whose stem matches the entry name (`[file.egpu-prime]` →
`egpu-prime.service`). Zero or several matches fail lint, asking for an
explicit `source`.

## 5.3 Run arbitrary idempotent shell steps

> As an operator, I want an escape hatch to run a shell command idempotently — with
> a check that decides whether it's even needed — so that I can handle the
> long tail of system tweaks no dedicated cook covers.

### 5.3.1 bash skips apply when current state equals desired

`[bash.<name>]` declares an `apply` command, plus an optional `current_state`
command and a `desired_state` string. totchef runs the `current_state` probe; if its
output already equals `desired_state`, the step is skipped; otherwise `apply` runs.

### 5.3.2 bash with no current state always applies

With no `current_state`, the step is treated as "no check" and always applies.

### 5.3.3 bash guarded steps are no ops on rerun

Used in the example recipe for things like apt pinning, debconf preseeding,
and installing apt prerequisites — each guarded by a cheap state probe so re-runs are
no-ops.

### 5.3.4 bash is privilege agnostic root per entry

Privilege-agnostic: grant root per entry.

## 5.4 Install versioned commands onto the PATH

> As an operator, I want bundled tools installed as commands — system-wide or
> per-user — and updated only when their version changes, so that PATH tools roll
> forward deliberately instead of on every byte-twiddle.

### 5.4.1 usr local bin and local bin install command named after source stem

`[usr_local_bin.<name>]` installs a bundled asset to `/usr/local/bin` (always
as root); `[local_bin.<name>]` to `~/.local/bin`. Only `source` is declared:
the command takes the source's stem as its name and mode `0755`.

### 5.4.2 version decides the update not content

The diff key is the command's embedded version: an older (or unversioned, or
absent) install is rewritten; equal versions leave the file alone even when its
bytes differ. The report's `before`/`current`/`latest` columns carry the
versions.

A command that doesn't embed `__version__` or offer `--version`/`--help` is
rejected at lint ([§10.3.1](10_recipe_linting_rules.md)).

### 5.4.3 command may be any language even a binary

The contract markers (§10.3.1) are byte-level, so a bash script (`__version__="1.0"`), a
compiled binary with the marker baked in as a constant string, or anything else
qualifies — not just Python.

### 5.4.4 usr local bin is always root local bin is user scoped

`usr_local_bin` is an always-root cook (its domain is `/usr/local/bin`);
`local_bin` stays user-scoped.

### 5.4.5 source defaults to the bundled command named after the entry

With no `source`, the entry installs the unique bundled command whose stem
matches the entry name — `[local_bin.ctop]` needs no keys at all. Zero or
several matches fail lint, asking for an explicit `source`.

### 5.4.6 usr local sbin installs admin commands always as root

`[usr_local_sbin.<name>]` installs to `/usr/local/sbin` — the home of admin
and daemon helpers (e.g. a boot service's switch script), outside ordinary
users' PATH — always as root, under the same version contract.

## 5.5 Set specific lines in a config file

> As an operator, I want to own specific settings inside a config file another
> package ships — replacing just those lines and leaving the rest alone — so
> that I can tune a tool without templating its whole config.

### 5.5.1 conf replaces matching lines in place and appends missing ones

`[conf.<name>]` ensures each declared line is in `target`, keyed on the text
before `=` (a line without `=` keys on the whole line, so a section header
like `[Nala]` can be ensured too): a line with the same key is replaced in
place, a missing one is appended, and every other line — comments included —
is left untouched.

### 5.5.2 conf creates a missing target

A missing `target` is created (parents included) holding exactly the declared
lines.

### 5.5.3 conf rewrites only when a line differs

Diffed by content hash like `[file]`: a compliant file is never rewritten and
a `post_hook` fires only on a real change.

An entry declaring both `line` and `lines`, or neither, is rejected at lint
([§10.3.2](10_recipe_linting_rules.md)).
