# 12. [Installing agent skills](test_12_installing_agent_skills.py)

`[skills]` declares GitHub repos of Claude Code skills to keep installed, wrapping
the `skills` CLI (skills.sh) through `bunx` — the same tool an operator would
otherwise run by hand for each repo. totchef owns the declaration; the CLI owns
fetching and writing: skill files live once in the canonical `~/.agents/skills`
store — the source of truth any agent can share — with `~/.claude/skills/<skill>`
a symlink into it, and the lockfile at `~/.agents/.skill-lock.json` recording
what's installed.

## 12.1 Declare skill repos and keep them current

> As an operator, I want to declare which GitHub repos of skills I use, so that a
> fresh machine (or a stale one) gets them installed without me remembering the
> `skills add` invocation for each one — and I want the report to tell me, per
> skill, what changed.

### 12.1.1 skills installs each declared repo via the skills cli

`[skills] repos = [...]` installs each repo globally via
`bunx skills add <repo> -g --agent claude-code universal --skill '*' -y`, one
repo at a time. The extra `universal` target keeps the CLI in symlink mode — a
single-agent add silently switches to copy mode, stranding the canonical store.

### 12.1.2 skills requires bun and bunx and fails hard pointing at url bun

Requires both `bunx` (runs the `skills` CLI) and `bun` (links a cli-kind skill's
binary — see 12.1.9) to be present, depending on the `[url]` bun installer; if
either is missing, the run fails hard telling the operator the `[url]` bun install
must run first.

### 12.1.3 each skill gets its own report row with version and content id

A repo may hold many skills, each moving independently, so the report is one row
per skill, keyed `<repo>/<skill>`. The row's value is the skill's declared
version — read from the first manifest that states one: SKILL.md frontmatter
(top-level `version:` or nested under `metadata:`, block or flow style), then
package.json, then pyproject.toml — plus a short `#hash` content id from
the CLI lockfile's `skillFolderHash`, the GitHub tree SHA of the skill's
folder. Rows are per skill from the very first install:
the pre-sync placeholder for a fresh repo is split into the skills its
`skills add` just landed.

### 12.1.4 an installed skill reports unchanged when only its timestamp moved

When a repo does get re-synced (its upstream state was unknown — see 12.1.14),
the CLI rewrites every skill's lockfile `updatedAt` whether or not anything
changed — so the diff rests on `skillFolderHash` alone, and a skill whose hash
held still reports back as unchanged.

### 12.1.5 an installed skill reports upgraded when its content hash changed

When a skill's `skillFolderHash` moves (its folder's content actually changed
upstream), that skill's row reports upgraded.

### 12.1.6 the run log breaks down which skills were new updated or unchanged

Each repo's sync logs which of its skills were newly added, which had a changed
content hash, and which were untouched — read from the lockfile before and after
that repo's `skills add` ran.

### 12.1.7 a failed repo reports hard naming the failed repo

If `skills add` fails for a repo (an inaccessible or renamed GitHub source), the
run reports a hard failure naming it.

### 12.1.8 multiple repos install concurrently

Each declared repo is installed in its own `skills add` invocation; multiple
repos run concurrently rather than one after another.

### 12.1.9 a cli-kind skill binary is chmod and linked onto path

A skill that ships its own `package.json` with a `bin` entry (a "cli"-kind skill,
e.g. `peek`) gets its files installed by the `skills` CLI, but the CLI never
chmods that binary executable or puts it on PATH. On every sync the cook chmods
each installed skill's declared `bin` script(s) executable and runs `bun link`
from within the skill's canonical store directory, so the binary resolves on PATH.
A package.json without a `bin` entry is not a CLI and is left unlinked.
This is best-effort and idempotent, like bun's own node shim (§4.3.4): it runs
even on a converged re-run that skipped the CLI entirely (12.1.11), so the link
is restored if it was removed.

### 12.1.10 a plan shows one repo row before install and per skill rows after

A never-installed repo's skills can't be known before its first `skills add`,
so a plan for it shows a single `<repo>` row as "would install"; once
installed, the lockfile knows the repo's skills and a plan shows one row per
skill (as "would sync" when upstream is unreachable — see 12.1.12/12.1.13 for
the reachable cases).

### 12.1.11 an up run skips the cli when upstream content matches

Before syncing, the chef asks GitHub for each installed repo's tree — one
unauthenticated API call per repo, the same endpoint the `skills` CLI's own
`update` command uses. A repo whose skills' upstream folder SHAs all match the
lockfile has nothing to do: `skills add` is not invoked at all, and its skills
report unchanged. (The CLI-binary linking of 12.1.9 still runs.)

### 12.1.12 a plan shows up to date when upstream matches

With upstream reachable and a skill's folder SHA matching the lockfile, a plan
shows that skill as up-to-date rather than the blanket "would sync".

### 12.1.13 a plan shows would upgrade when upstream content changed

When a skill's upstream folder SHA differs from the lockfile, a plan shows it
as "would upgrade" with the upstream short content id in the latest column.

### 12.1.14 when github is unreachable every repo re-syncs

The upstream check is best-effort and tokenless — deliberately, so it can
never trigger a credential prompt. If the trees call fails (offline, rate
limited), the latest state is unknown and the cook falls back to
refresh-every-run: `skills add` re-runs for every declared repo, exactly as if
no check existed.

### 12.1.15 a drifted agent entry re-adds to restore the store symlink

`~/.claude/skills/<skill>` must be the symlink into the canonical store;
anything else — say a real-directory copy left by an older install — is drift.
A drifted skill plans as "would sync" even when upstream matches, and `up`
re-adds its repo, letting the CLI replace the entry with the symlink.

### 12.1.16 a re-add reports a newly landed skill as its own installed row

A skill first appearing during a re-add of an already-installed repo (upstream
added it) gets its own per-skill row, reporting "installed" — not just the sync
log mention of 12.1.6.
