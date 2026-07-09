"""knip config governance: a repo's knip settings live in standalone files,
never inline in `package.json`, so they read the same way `ruff.toml`/
`.rumdl.toml` do. A bare `knip.json` is optional and, if present, may only
set the keys in `ALLOWED_CUSTOMIZATIONS`, each drawn from its shared
allowance: `ignoreBinaries` for system-level tools every org repo may shell
out to from JS/TS scripts (knip flags them as unlisted binaries because
they are deliberately not npm dependencies and missing from knip's built-in
global-binary list), and `ignoreDependencies` for packages knip cannot see
being consumed. Knip's own defaults remain the baseline; every other
customization stays forbidden.

A second file, `knip.prod.json`, runs knip's entry-exports pass with the test
harness excluded: `includeEntryExports` makes knip check a workspace's own
`exports["."]` surface for dead/test-only exports, which knip otherwise treats
as an intentional public API — correct for a genuinely published package,
wrong for everything else. `ignoreWorkspaces` drops every `tests/*` workspace
member from the graph entirely, so an export reachable only from a test
workspace reads as unused rather than used — this org tears every package's
tests out to its own `tests/<basename>` workspace, so excluding those members
is exactly "only production code counts." The workspaces exempted from
`includeEntryExports` must match exactly the npm-kind targets declared in
`release-targets.toml` — those packages have consumers outside the monorepo
this pass can't see. `--config` replaces knip's config wholesale rather than
layering on top of `knip.json` (knip has no `extends`), so this file must also
repeat the repo's `knip.json` content verbatim — otherwise this pass would
flag things the base pass was told to ignore. It may additionally set
`"exclude": ["catalog"]`: with tests out of the graph, test-only catalog
entries would read as unused, and the base pass already checks the catalog
with tests visible.
"""

from __future__ import annotations

import json
import tomllib
from typing import TYPE_CHECKING, Any

from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "knip-config"
SUMMARY = (
    "knip config is standalone (never inline in package.json) and its prod pass exempts "
    "exactly the repo's published npm targets"
)
SCOPE = Scope.CONTENT

PACKAGE_JSON = "package.json"
BASE_CONFIG = "knip.json"
PROD_CONFIG = "knip.prod.json"
_RELEASE_TARGETS = "release-targets.toml"
_REQUIRED_IGNORE_WORKSPACES = ["tests/*"]
_PROD_EXTRA_KEYS = frozenset({"$schema", "workspaces", "exclude"})
# The prod pass may exclude exactly the catalog issue type: with `ignoreWorkspaces: ["tests/*"]`
# knip cannot see test usage of catalog entries, so test-only entries would read as unused —
# the base pass, which keeps tests in the graph, still checks the catalog.
_PROD_ALLOWED_EXCLUDE = ["catalog"]
_OK_MESSAGE = (
    "knip.json (if any) stays within the shared allowances; knip.prod.json exactly exempts every published npm target"
)

# Per-key allowances any org repo may draw from in its knip.json.
# ignoreBinaries: system-level tools invoked from JS/TS scripts without being npm dependencies;
# knip's built-in global-binary list covers docker/git/curl/… but not these.
# ignoreDependencies: packages consumed in ways knip cannot trace.
ALLOWED_CUSTOMIZATIONS: dict[str, frozenset[str]] = {
    "ignoreBinaries": frozenset({"podman", "uv"}),
    "ignoreDependencies": frozenset({"cloudflare"}),
}


def _without_schema(parsed: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in parsed.items() if key != "$schema"}


def _npm_workspace_dirs(manifest: str) -> set[str]:
    try:
        data = tomllib.loads(manifest)
    except tomllib.TOMLDecodeError:
        return set()
    targets = data.get("target")
    if not isinstance(targets, list):
        return set()
    dirs: set[str] = set()
    for entry in targets:
        if not isinstance(entry, dict) or entry.get("kind") != "npm":
            continue
        version = entry.get("version")
        file = version.get("file") if isinstance(version, dict) else None
        if isinstance(file, str) and file.endswith(f"/{PACKAGE_JSON}"):
            dirs.add(file[: -len(f"/{PACKAGE_JSON}")])
    return dirs


def _check_no_inline_key(manifest: dict[str, Any], res: CheckResult) -> None:
    if "knip" in manifest:
        res.fail(f'{PACKAGE_JSON} must not have a "knip" key; move its content to a standalone {BASE_CONFIG}')


def _check_base_config(repo: Repo, ctx: Context, res: CheckResult) -> dict[str, Any]:
    """Validate knip.json against the shared allowance; return its content ($schema aside) for the prod pass."""
    content = ctx.file(repo, BASE_CONFIG)
    if content is None:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        res.error(f"could not parse {BASE_CONFIG}: {exc}")
        return {}
    if not isinstance(parsed, dict):
        res.error(f"{BASE_CONFIG} must be a JSON object")
        return {}
    base = _without_schema(parsed)
    stray_keys = sorted(set(base) - set(ALLOWED_CUSTOMIZATIONS))
    if stray_keys:
        allowed_keys = ", ".join(f'"{key}"' for key in ALLOWED_CUSTOMIZATIONS)
        res.fail(f"{BASE_CONFIG} may only customize {allowed_keys}; unexpected key(s): {', '.join(stray_keys)}")
    for key, allowance in ALLOWED_CUSTOMIZATIONS.items():
        names = base.get(key)
        if names is None:
            continue
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            res.fail(f'{BASE_CONFIG} "{key}" must be a JSON array of strings')
            continue
        outside = sorted(set(names) - allowance)
        if outside:
            res.fail(
                f"{BASE_CONFIG} {key} allows only {', '.join(sorted(allowance))}; not allowed: {', '.join(outside)}"
            )
    return base


def _workspace_exemptions(workspaces: object) -> tuple[set[str], list[str]]:
    """Split a `workspaces` map into exact `{"includeEntryExports": false}` entries vs. malformed ones."""
    exempted: set[str] = set()
    malformed: list[str] = []
    if isinstance(workspaces, dict):
        for key, cfg in workspaces.items():
            if not isinstance(key, str):
                continue
            if cfg == {"includeEntryExports": False}:
                exempted.add(key)
            else:
                malformed.append(key)
    return exempted, malformed


def _check_workspace_exemptions(repo: Repo, ctx: Context, parsed: dict[str, Any], res: CheckResult) -> None:
    manifest = ctx.file(repo, _RELEASE_TARGETS)
    published = _npm_workspace_dirs(manifest) if manifest is not None else set()
    workspaces = parsed.get("workspaces")
    if workspaces is not None and not isinstance(workspaces, dict):
        res.fail(f'{PROD_CONFIG} "workspaces" must be a JSON object')
    exempted, malformed = _workspace_exemptions(workspaces)
    if malformed:
        res.fail(
            f'{PROD_CONFIG} workspaces entries must be exactly {{"includeEntryExports": false}}: '
            f"{', '.join(sorted(malformed))}"
        )
    missing = sorted(published - exempted)
    if missing:
        res.fail(f"{PROD_CONFIG} workspaces must exempt published target(s): {', '.join(missing)}")
    extra = sorted(exempted - published)
    if extra:
        res.fail(f"{PROD_CONFIG} workspaces exempts non-published dir(s): {', '.join(extra)}")


def _check_prod_config(repo: Repo, ctx: Context, base: dict[str, Any], res: CheckResult) -> None:
    content = ctx.file(repo, PROD_CONFIG)
    if content is None:
        res.fail(f"no {PROD_CONFIG} at repo root — needed to catch dead/test-only exports")
        return
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        res.error(f"could not parse {PROD_CONFIG}: {exc}")
        return
    if not isinstance(parsed, dict):
        res.error(f"{PROD_CONFIG} must be a JSON object")
        return

    required = {
        **base,
        "includeEntryExports": True,
        "ignoreWorkspaces": _REQUIRED_IGNORE_WORKSPACES,
    }
    stray_keys = sorted(set(parsed) - set(required) - _PROD_EXTRA_KEYS)
    if stray_keys:
        res.fail(f"{PROD_CONFIG} has unexpected key(s): {', '.join(stray_keys)}")
    for key, expected in required.items():
        if parsed.get(key) != expected:
            res.fail(f'{PROD_CONFIG} must set "{key}": {json.dumps(expected)}')
    exclude = parsed.get("exclude")
    if exclude is not None and exclude != _PROD_ALLOWED_EXCLUDE:
        res.fail(f'{PROD_CONFIG} "exclude" (if any) must be exactly {json.dumps(_PROD_ALLOWED_EXCLUDE)}')

    _check_workspace_exemptions(repo, ctx, parsed, res)


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    root = ctx.file(repo, PACKAGE_JSON)
    if root is None:
        res.skip("no package.json")
        return res
    try:
        manifest = json.loads(root)
    except json.JSONDecodeError as exc:
        res.error(f"could not parse {PACKAGE_JSON}: {exc}")
        return res
    if not isinstance(manifest, dict):
        res.error(f"{PACKAGE_JSON} must be a JSON object")
        return res

    _check_no_inline_key(manifest, res)
    base = _check_base_config(repo, ctx, res)
    _check_prod_config(repo, ctx, base, res)

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
