# Copilot code review instructions

Only post medium- and high-severity review comments. Do not post low-severity or nitpick comments.

This project targets Python 3.14 and uses modern syntax. Before flagging any syntax as invalid, verify it against Python 3.14 — recent additions such as PEP 758 unparenthesized `except A, B, C:` clauses and the `type` alias statement are valid here.

Before claiming that an API of a dependency does not exist or is unsupported, verify it against the version pinned in this repo's lockfile — do not flag documented APIs of installed versions as nonexistent. For example, this repo uses Vitest 4, where `test.for(...)` is a supported parameterized-test API (preferred over `test.each` when the callback needs the fixture context).

Do not flag code based on hedged claims about external API runtime behavior (e.g., a GitHub API field being "often null" for some event type) unless the behavior is documented and definitive. In this repository, workflow runs triggered by the `release` event report `head_branch` as the release tag name.

Before reporting that a regex matches (or misses) a given input, trace the match mechanically against the pattern's anchoring — do not infer a false positive from surface resemblance (e.g. a pattern requiring `sh` immediately after `\|\s*` cannot match `| ssh`). The same applies to claimed stdlib failure modes: verify the documented behavior first (e.g. `Path.touch()` with the default `exist_ok=True` succeeds on an existing directory via `os.utime`).

The mandatory `ci` check runs the full quality gate on every push: ruff (`select = ["ALL"]`), pyrefly, vulture, knip, tsc, eslint, rumdl, and both test suites. Do not report syntax, typechecking and linting errors - leave these to the deterministic ci gate.

Don't flag long lines or long docstrings — ruff's line-length check is enforced deterministically in `ci` and will catch anything that's actually too long; a style comment here is redundant noise.

Don't suggest guards for exceptions an API can't raise. Non-strict pathlib calls (`resolve()`, `exists()`, `is_symlink()`) swallow `OSError` by documented contract — a `try/except OSError` around them is dead code. Verify an exception is actually reachable before proposing a handler for it.

`apps/totchef` (a declarative, idempotent system-configuration tool) has two conventions specific to it — do not flag these as defects:

- **Cooks that front an external CLI replicate that CLI's exact path semantics** — no extra `~`-expansion, normalization, or fallbacks the CLI doesn't do. Drift detection must see byte-for-byte the paths the CLI writes; "hardening" that diverges creates false drift. Check the fronted tool's source before suggesting path handling changes.
- **`apps/totchef/examples/totchef_files/*.py` are standalone `uv` scripts**, deployed verbatim and run via their own inline `# /// script` dependencies. Their imports are not library dependencies and belong out of `[project.dependencies]`.
