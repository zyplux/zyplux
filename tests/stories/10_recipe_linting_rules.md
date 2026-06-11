# 10. [Recipe linting rules](test_10_recipe_linting_rules.py)

`totchef lint` is the recipe's gatekeeper: it validates the file against every
cook's schema and the dependency graph without touching the system. The same
checks run at the start of every `plan` and `up` (§1.1.4), so each criterion
below is a rule the recipe must satisfy before anything else happens.

A few cook rules are specified inline where their cook's behavior lives:
a relative URL without `url` (§5.1.5), `content` and `source` together
(§5.2.1), and a missing or ambiguous default bundled source (§5.2.6, §5.4.5).

## 10.1 Validate a recipe without running it

> As an operator, I want to check that my recipe is well-formed before I rely on
> it, so that a typo fails fast instead of mid-run.

### 10.1.1 lint validates and prints path valid

`totchef lint` validates the recipe against every cook's schema and the
dependency graph, then prints `<path>: valid` or exits with a precise error.

### 10.1.2 lint needs no root and changes nothing

Linting needs no root and changes nothing — no file is written and no shell
command runs.

## 10.2 Have structural mistakes rejected with a precise error

> As an operator, I want any structural mistake in my recipe — wrong section,
> typo'd key, bad dependency, misplaced root grant — rejected with a message
> that explains how to fix it, so that errors surface before anything runs.

### 10.2.1 every section names a registered cook and every key is known

A section must name a registered cook, and every recipe key must be one the
cook declares — an unknown or misspelled key is rejected (`extra='forbid'`)
rather than silently ignored.

### 10.2.2 dependencies name existing nodes with no cycles or self dependencies

A `depends_on` must name a node that exists; a dependency cycle or a node
depending on itself is rejected, with a message that explains how to fix it.

### 10.2.3 needs root sits on a leaf entry never a subtable header

`needs_root` is **forbidden** on a subtable section header, because that would
grant root to every entry wholesale — it must be set per leaf entry (least
privilege), and the error says so.

### 10.2.4 remove how requires remove when

`remove_how` without `remove_when` is an orphan instruction; lint rejects it
naming the missing condition.

## 10.3 Have cook contracts enforced statically

> As an operator, I want each cook's own entry rules enforced at lint time —
> statically, without anything executing — so that a bad entry never reaches
> an apply.

### 10.3.1 bin commands embed a version or offer help

A command that doesn't embed `__version__ = "<version>"` or offer
`--version`/`--help` can't enter a bin cook: lint rejects the entry. The check
is static — read off the file's bytes, never executing it.

### 10.3.2 conf entries declare exactly one of line or lines

A `conf` entry declares a single `line` or a `lines` array — declaring both,
or neither, is rejected.

### 10.3.3 cook entry model violations are reported per node and location

A cook declares an `entry_model` (a pydantic model with `extra='forbid'`);
lint validates each node's recipe slice against it and reports every violation
as a precise `[node] location: message` line. This is what makes a cook
author's schema bite: an operator's typo fails the lint instead of being
silently ignored.
