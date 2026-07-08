# 11. [Managing dotfiles with chezmoi](test_11_managing_dotfiles.py)

## 11.1 Provision dotfiles from a git repo

> As an operator, I want to declare my dotfiles git repo and have totchef clone it with
> chezmoi and keep its config in sync — idempotently — so my machine tracks the repo from
> one recipe section. The sync is one-way: `$HOME` flows into the repo (§11.3), never the
> reverse — seeding `$HOME` from the repo is a rare fresh-machine step I do by hand with
> `chezmoi apply`.

### 11.1.1 chezmoi clones the repo into the source dir

`[chezmoi]` with a `repo` clones it into the source directory (`chezmoi init`) and writes
chezmoi's config, but never writes into `$HOME` — the flow is one-way, `$HOME` → repo.

```toml
[chezmoi]
repo = "https://github.com/operator/dotfiles.git"
```

### 11.1.2 source dir is configurable and written to chezmoi config

`source_dir` sets where chezmoi clones and reads the dotfiles (defaulting to chezmoi's own
`~/.local/share/chezmoi`). It is passed to chezmoi and persisted as `sourceDir` in
`~/.config/chezmoi/chezmoi.toml`, alongside a pinned `umask` — chezmoi derives a file's mode
from `0o666 &^ umask`, so pinning it keeps a later manual `chezmoi apply` deterministic
regardless of the operator's login umask.

```toml
[chezmoi]
repo = "https://github.com/operator/dotfiles.git"
source_dir = "~/dotfiles"
```

### 11.1.3 chezmoi is idempotent once provisioned

A re-run is a no-op: once the source directory holds the clone, the config matches, and the
capture timer is enabled, the resource shows `unchanged` and neither `init` nor the capture
setup runs again.

## 11.2 Run as the operator with the binary in place

> As an operator, I want chezmoi to manage my own `$HOME` (never root's) and to fail loudly
> when the chezmoi binary isn't installed yet, so the dependency on the installer is obvious.

### 11.2.1 chezmoi is user scoped not root

`[chezmoi]` ships as a custom cook discovered from the recipe's `totchef_cooks/` (not a
built-in — it's the canonical highly-custom cook): it manages the operator's `$HOME`, so it
lists with `user` scope (origin `local`) and never escalates to root.

### 11.2.2 chezmoi without the binary fails clearly

When the `chezmoi` binary isn't on the operator's PATH — the `[url.chezmoi]` installer hasn't
run — the resource hard-fails with a message naming the section that must run first, instead
of silently doing nothing.

## 11.3 Capture home edits back to the repo automatically

> As an operator, I want chezmoi to capture the changes I make in `$HOME` on a schedule and
> commit and push them on its own, so that working normally keeps my dotfiles repo up to date
> without my running git or systemctl by hand.

### 11.3.1 auto commit and push are on and written to chezmoi git config

The cook persists `autoCommit`/`autoPush` to the `[git]` section of
`~/.config/chezmoi/chezmoi.toml`, so the scheduled `chezmoi re-add` commits the captured
changes and pushes them to the remote with no extra steps.

```toml
[chezmoi]
repo = "https://github.com/operator/dotfiles.git"
```

### 11.3.2 capture units install and the timer is enabled

The cook installs a systemd *user* service+timer (generated in code) into
`~/.config/systemd/user` — a timer that runs `chezmoi re-add` periodically and the service it
triggers. It enables the timer without a session D-Bus by writing the `timers.target.wants`
symlink `systemctl --user enable` would create, then best-effort starts it (it otherwise
activates on next login).

### 11.3.3 capture is idempotent once enabled

Once the units are installed and the timer enabled (its wants-symlink present), a re-run shows
`unchanged`: the cook neither rewrites the units nor re-runs `systemctl start`.

### 11.3.4 timer cadence comes from timer min

`timer_min` sets the timer's `OnUnitActiveSec`, so the operator tunes how often `$HOME` is
captured; editing it rewrites the unit and restarts the timer.

```toml
[chezmoi]
repo = "https://github.com/operator/dotfiles.git"
timer_min = 60
```

### 11.3.5 timer min must be positive

`timer_min` is a positive number of minutes; `0` or negative is rejected at lint, since a
zero-interval capture timer is invalid.
