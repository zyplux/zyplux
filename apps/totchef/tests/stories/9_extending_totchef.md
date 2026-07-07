# 9. [Extending totchef (cook authors)](test_9_extending_totchef.py)

## 9.1 Add a new configuration domain as a plugin

> As a cook author, I want to add a new recipe section backed by my own cook, so
> that totchef can manage a domain it doesn't ship with.

### 9.1.1 cook registered under entry point group serves its section

A cook is a `CookBase` subclass registered under the `totchef.cooks`
entry-point group; the section name it serves is the entry-point name. Built-in and
third-party cooks register the same way, and `totchef cooks` shows the origin.

## 9.2 Prototype a cook without packaging it

> As a cook author, I want to drop a single Python file beside my recipe (or into my config
> dir) and have totchef pick it up, so that I can carry a highly custom cook with my recipe —
> or prototype a domain — without building a package.

### 9.2.1 local cook file is picked up and shadows a builtin

A loose `~/.config/totchef/cooks/<section>_cook.py` (containing exactly one
`CookBase` subclass; the `_cook`/`_root_cook` suffix is stripped to derive the
section) is loaded as a local cook and **shadows** a built-in of the same name — an
escape hatch for overriding or prototyping.

### 9.2.2 custom cook loads from totchef cooks beside the recipe

A loose `<section>_cook.py` in the recipe's sibling `totchef_cooks/` is discovered and serves
its section — the primary way a recipe repo carries highly custom cooks (e.g. `chezmoi`)
without packaging them. It takes precedence over a built-in or config-dir cook of the same
name.

## 9.3 Choose the right cook shape for my domain

> As a cook author, I want base classes that match common patterns, so that I only
> implement the domain-specific probe/act logic and inherit diffing, scheduling,
> and reporting.

### 9.3.1 versioned cook implements requested installed latest sync

**VersionedCook** for versioned packages: implement
`list_requested`/`list_installed`/`find_latest`/`sync`. `PackageListCook` covers
plain `packages = [...]` sections.

### 9.3.2 state cook implements current desired apply filestate diffs

**StateCook** for desired-state resources: implement
`get_current_state`/`get_desired_state`/`apply_resource` (+ hooks). `FileStateCook`
already diffs by sha256 of rendered bytes vs the on-disk file — a subclass just
supplies the target path and the rendered content.

### 9.3.3 cook only probes and acts orchestrator owns the diff

The cook only *probes* and *acts*; the orchestrator owns every diff and
idempotency decision, so a cook holds no diff logic.

*Getting a typo'd recipe rejected against a cook's `entry_model` is specified
in [§10.3.3](10_recipe_linting_rules.md).*
