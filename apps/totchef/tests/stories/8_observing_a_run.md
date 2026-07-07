# 8. [Observing a run](test_8_observing_a_run.py)

## 8.1 See a clear, color-coded report of what happened

> As an operator, I want a readable summary table at the end of a run, so that I can
> tell at a glance what was installed, upgraded, applied, or left alone.

### 8.1.1 report table color coded on terminal plain toon otherwise

The report is a table with `cook-node`, `before`, `current`, `latest`, and
`action` columns. `before` is the state snapshot from before the cook acted;
`current` is the state right now (post-sync on `up`, equal to `before` on
`plan` since no action has happened); `latest` is the upgrade target. On an
interactive terminal it's a rich table with color-coded actions (green for
installed/upgraded/applied, yellow for "would …", red for failures, dim for
unchanged); on a non-terminal it's plain TOON text.

### 8.1.2 up shows changed rows plus footer plan shows all

A real `up` shows only changed/failed rows plus a footer counting unchanged
resources and total elapsed time; a `plan` shows every row.

### 8.1.3 content hash diffs humanized matches or differs

Content-hash diffs are humanized — a hash equal to the rendered recipe content
reads `matches`, a drifting one reads `differs`, a missing file reads `absent`,
and the `latest` cell shows the target's short content id (`#1a2b3c4d`), so a
row distinguishes "exists with the wrong content" from "doesn't exist yet".

### 8.1.4 before and current diverge on upgrade

After an `up` that upgrades a resource, the `before` cell shows the pre-sync
version and the `current` cell shows the post-sync version, so the row reads
as a real diff (e.g. `url.claude,2.1.152,2.1.153,—,upgraded`). `current` is a
fresh post-sync probe — not a copy of `before` — so the column reflects what
is installed right now.

### 8.1.5 failed install keeps before equal current

When an install errors, the row reads `before == current ≠ latest` — both
sides show `(none)` because nothing landed, while `latest` shows the unmet
target. The operator can see at a glance that the requested version did not
arrive.

## 8.2 Watch progress while a long run executes

> As an operator, I want live feedback during a run, so that I know it's working and
> roughly how far along it is.

### 8.2.1 transient progress bar cleared on exit

On an interactive terminal, a transient progress bar shows completed/total
resources and elapsed time; it's cleared on exit, leaving the logs above it.

### 8.2.2 log lines colorized and tagged per cook

Each cook's log lines are colorized and tagged with the cook's name in a stable
per-cook color, so the interleaved output of concurrently-running cooks stays
readable.

### 8.2.3 start and completion lines announce waits and unblocks

Start lines announce who is running (and, for user nodes, what they're waiting
on and what they unblock); completion lines report timing and which downstream
resources just unlocked.

## 8.3 Keep a timestamped log of every run

> As an operator, I want each run recorded to a log file owned by me, so that I can
> audit or debug after the fact, even though the apply ran as root.

### 8.3.1 timestamped log under user state dir chowned back

Each run writes a timestamped log under the invoking user's state dir
(`~/.local/state/totchef/logs/`), resolved from `SUDO_USER` so a root re-exec still
logs to the user's home, then chowned back to the user.

### 8.3.2 all output funnels through a single pump

All output — the parent's and every forked cook's stdout/stderr — funnels
through a single pump so log lines never interleave with the live table/progress
region.

### 8.3.3 dry run shows only plan on terminal but logs everything

A dry run shows only the version banner (§8.3.5) and the plan table on the
terminal while still recording every line to the log file.

### 8.3.4 a failed run names its log file

When a run ends in failure, the final summary line names the run's log file path —
both the hard-failure `apply aborted` line and the soft-failure summary — so an
operator who saw only the report knows exactly which file to open to read the
captured error.

### 8.3.5 every run logs the totchef version up front

Every `plan`/`up` logs `totchef <version>` as its first line and echoes it to
the terminal ahead of any table — even on a dry run, whose other log lines stay
off the terminal (§8.3.3). The version comes from the package metadata — the
same single source of truth `--version` reports (§1.5).

## 8.4 See follow-up actions after the report

> As an operator, I want any "do this next" notices — restart an app, reboot
> the machine — gathered in one block after the report table, so that they
> don't scroll away with the run's logs.

### 8.4.1 delayed messages print after the report labeled by cook node

A cook returns an optional `delayed_message` on its outcome
(`SyncOutcome`/`StateChangeOutcome`). The runner logs it live as the cook
completes — keeping the in-session reminder — and repeats every collected
message in an `Action required` block after the report table, labeled with
its cook node. No messages, no block; a dry run collects none.
