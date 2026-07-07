# 2. [Authoring a recipe](test_2_authoring_a_recipe.py)

## 2.1 Declare the machine I want in one TOML file

> As an operator, I want the entire machine configuration expressed in a single
> declarative `recipe.toml`, so that the file is the single source of truth and a
> fresh clone reproduces the working state.

### 2.1.1 each section maps to a cook plain vs subtable

Each top-level section (`[apt_pkg]`, `[url.bun]`, `[file.grub_deep_sleep]`, …)
maps to a cook that manages that domain. A plain-data section is one unit of work; a
subtable section (`[url.<name>]`) fans out to one unit per entry.

### 2.1.2 operator declares desired state not steps

The operator never writes imperative steps — only the desired end state. The
tool computes the diff and the order.

### 2.1.3 package sections split into named entries

A `packages = [...]` section (`[apt_pkg]`, `[cargo]`, `[uv]`, …) can fan out
like any subtable: `[apt_pkg.<group>]` makes each group its own unit of work
with its own `packages` and `depends_on`, so a small group can unblock its
dependants without waiting for the rest of the section.

## 2.2 Express ordering between resources

> As an operator, I want to declare that one resource must be configured before
> another, so that, for example, apt repos exist before packages from them are
> installed.

### 2.2.1 depends on names entry node or section

Any entry can carry `depends_on = [...]`, naming another entry
(`bash.apt_prereqs`), a single-node section (`apt_pkg`), or a whole section
(`apt_repo`) which fans out to all of its entries.

### 2.2.2 resources run in topological order

totchef builds a dependency DAG and runs resources in topological order; a
node only starts once all of its dependencies have succeeded.

A bad dependency — a missing node, a cycle, a self-dependency — is caught at
lint ([§10.2.2](10_recipe_linting_rules.md)).

## 2.3 Set shared defaults across a section's entries

> As an operator, I want to set options once at the section level and have each
> entry inherit them, so that I don't repeat the same flags on every app.

### 2.3.1 section defaults fold into entries lists extend others override

A subtable section's own scalar/list keys become defaults folded into each
entry's slice. For lists (e.g. shared GPU `features`), the entry **extends** the
shared list; for everything else, the entry **overrides** the default.

### 2.3.2 shared desktop features yield union per entry

Example: `[desktop]` declares a shared `features = [...]`, and
`[desktop.brave]` adds a couple more — Brave ends up with the union.

## 2.4 Grant root only where it's needed

> As an operator, I want privilege granted per resource at the finest grain, so
> that a user-scoped step never runs as root unnecessarily.

### 2.4.1 needs root per entry escalates a privilege agnostic cook

Whether a cook needs root is driven by the cook's own `needs_root` attribute,
but a recipe entry can also set `needs_root = true` to escalate a privilege-agnostic
cook (`bash`, `file`) for that one entry.

`needs_root` on a subtable section header is forbidden — lint rejects it
([§10.2.3](10_recipe_linting_rules.md)).

## 2.5 Declare when a temporary entry expires

> As an operator, I want a temporary workaround entry to declare the upstream
> condition that makes it obsolete, so that every run tells me the moment it
> can be removed instead of me re-checking upstream by hand.

### 2.5.1 remove when satisfied surfaces remove how in action required

Any entry can carry `remove_when` (a shell probe; exit 0 means "the thing this
entry waits on has happened") and `remove_how` (the operator instruction for
dismantling it). While the probe exits non-zero the run is silent about it —
and a *failing* probe (no network, missing tool, timeout) reads the same, so
an outage never fabricates a removal notice. Once it exits 0, the instruction
lands in the `Action required` block labeled with the node, on every run until
the entry is deleted. Probes run as the invoking user (their `gh` auth, their
network identity), even for `needs_root` entries.

### 2.5.2 plan also evaluates remove when

A dry run evaluates the probes too, so `plan` doubles as "check everything I'm
waiting on" without touching the system. With no `remove_how`, a fired watch
carries the generic notice that the entry can be removed.

### 2.5.3 any entry or plain section can carry remove when

`remove_when`/`remove_how` sit on the base entry contract, so every cook
accepts them — a subtable entry (`[file.<name>]`) and a plain-data section
(`[uv]`) alike.

`remove_how` without `remove_when` is rejected at lint
([§10.2.4](10_recipe_linting_rules.md)).
