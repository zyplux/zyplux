# 7. [Safety, correctness, and trust](test_7_safety_correctness_and_trust.py)

## 7.1 Trust that re-runs only change what drifted

> As an operator, I want every run to be safe to repeat, so that I can run totchef
> on a schedule or whenever I'm unsure, without fear of redundant or destructive
> work.

### 7.1.1 cooks probe and act only on the difference

Every cook **probes** current state and acts only on the difference. Versioned
cooks skip up-to-date packages; state cooks skip resources whose content hash already
matches. The `url` cook is the exception: it diffs presence, not version, so a present
tool re-runs its `update_action` each run rather than being skipped (§3.3.1).

### 7.1.2 post hooks fire only on actual change

`post_hook`s fire only on actual change, so expensive refreshes don't run on
no-op passes.

## 7.2 Understand that totchef creates and updates but never prunes

> As an operator, I want to know that removing a section from my recipe leaves the
> existing artifact in place, so that I'm not surprised by what teardown does (and
> doesn't) happen.

### 7.2.1 convergence is create update only never prunes

Convergence is **create/update only**. Dropping an entry from the recipe (or
uninstalling its target) leaves prior artifacts — a written `/etc` drop-in, a repo's
keyring + `.sources`, a `.desktop` override — in place. Teardown is manual and
deliberate.

## 7.3 Escalate to root only for the apply, and drop privilege otherwise

> As an operator, I want totchef to request root only when applying, and to run
> each user-scoped step as me rather than as root, so that the privilege surface is
> minimal and files land with the right ownership.

### 7.3.1 up re execs under sudo pinning recipe and log

`totchef up` re-execs itself under `sudo`, pinning the already-resolved recipe
path and shared log file across the boundary so root sees the same file.

### 7.3.2 forked child drops privilege for user nodes

Each resource runs in a forked child: a `needs_root` child keeps root; every
other child **drops privilege** back to the invoking user (gid → groups → uid) and
repoints `HOME`/`USER`/`PATH`. So user files are written as the user, and freshly
bootstrapped toolchains (`~/.cargo/bin`, `~/.bun/bin`, `~/.local/bin`) are found on
the next step's PATH.

### 7.3.3 plan and lint never escalate

`plan` and `lint` never escalate.

### 7.3.4 frozen binary re execs by absolute path not argv0 name

A frozen single-file binary (`just build`'s PyInstaller bundle) is invoked by bare
name on `PATH`, so `sys.argv[0]` is just `"totchef"` while `sys.executable` is the
resolved absolute path. The sudo re-exec must run that absolute `sys.executable`
(sudo's `secure_path` can't find a bare name, and an absolute path bypasses the
search) followed by only the user's args (`argv[1:]`) — never the bare `argv[0]`,
which sudo would treat as a command to look up or Typer as a bogus sub-command.

## 7.4 Distinguish recoverable failures from fatal ones

> As an operator, I want failures classified by severity, so that a cosmetic
> hiccup doesn't abort my whole run but a real problem does.

### 7.4.1 hard failure aborts the apply and exits 1

**Hard failure** aborts the apply and exits `1` (e.g. a requested package
isn't available anywhere, a `bash apply` command errors, a `uv` tool install fails).

### 7.4.2 soft failure warns finishes and exits 75

**Soft failure** warns, finishes the run, and exits `75` (e.g. a snap
*refresh* failed, a `post_hook` failed, a target file held invalid JSON).

### 7.4.3 report names which cooks hard or soft failed

The end-of-run report names which cooks hard- or soft-failed.

### 7.4.4 a crash outside any cook still reports loudly

An unexpected exception outside any cook is a totchef bug, not a recipe
failure: the run still exits `1` with the full traceback logged to the
terminal and the log file — never a silent death.

## 7.5 Skip steps that shouldn't run right now

> As an operator, I want a guard that can skip a step when a precondition isn't met,
> so that, for example, a browser config isn't rewritten while the browser is
> running.

### 7.5.1 pre hook nonzero exit skips the item

State-cook entries support a `pre_hook` guard: a non-zero exit **skips** the
item (reported as `skipped`, not failed) — a benign skip, not an error.

### 7.5.2 cooks compose intrinsic guards with pre hook

Cooks compose their own intrinsic guards with the operator's `pre_hook` (e.g.
the Chromium cook chains a "browser not running" check with any recipe-declared
guard).

### 7.5.3 hooks run on versioned sections too

`pre_hook`/`post_hook` are valid on every cook section, versioned ones included.
On a versioned section (`[cargo]`, `[bun]`, …) the `pre_hook` gates the whole
sync — a non-zero exit **skips** it — and the `post_hook` fires once after a
change (e.g. linking a freshly-installed binary onto `PATH`).
