"""knip config governance: settings live in standalone files, never inline in
`package.json`, the way `ruff.toml` and `.rumdl.toml` do. An optional
`knip.json` may set only the configured `allowed_customizations`, each drawn
from its shared allowance — `ignoreBinaries` for system tools JS/TS scripts
shell out to (deliberately not npm dependencies), `ignoreDependencies` for
packages knip cannot see consumed. Knip's defaults are the baseline.

`knip.prod.json` enforces one rule: a production export earns its place only
by being consumed by other production code, never by tests alone.
`includeEntryExports` puts a workspace's own `exports["."]` surface under
scrutiny instead of trusting it as public API, and `ignoreWorkspaces` drops
every member outside `[source].production_roots` — test harnesses, dev
tooling — so an export only they reach reads as unused. Any glob spelling
will do: what is checked is the members it resolves to — every non-production
workspace dropped, no production one with it. Published packages are the exception
and opt out of `includeEntryExports` one by one — exactly the npm-kind targets
in `release-targets.toml`, whose consumers live outside this repo.

Two mechanics: `--config` replaces knip's config wholesale (knip has no
`extends`), so this file must repeat `knip.json` verbatim; and it may set
`"exclude": ["catalog"]`, since catalog entries used only outside production
read as unused here and the base pass already checks the catalog.
"""

from __future__ import annotations

import json
import tomllib
from typing import TYPE_CHECKING, Any

import yaml

from cerberus import workspaces
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "knip"
SUMMARY = (
    "knip config is standalone (never inline in package.json) and its prod pass exempts "
    "exactly the repo's published npm targets"
)
SCOPE = Scope.CONTENT

PACKAGE_JSON = "package.json"
BASE_CONFIG = "knip.json"
PROD_CONFIG = "knip.prod.json"
_RELEASE_TARGETS = "release-targets.toml"
_PROD_EXTRA_KEYS = frozenset({"$schema", "workspaces", "exclude", "ignoreWorkspaces"})
_OK_MESSAGE = (
    "knip.json (if any) stays within the shared allowances; knip.prod.json exactly exempts every published npm target"
)


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
    customizations = ctx.config.knip_allowed_customizations
    stray_keys = sorted(set(base) - set(customizations))
    if stray_keys:
        allowed_keys = ", ".join(f'"{key}"' for key in customizations)
        res.fail(f"{BASE_CONFIG} may only customize {allowed_keys}; unexpected key(s): {', '.join(stray_keys)}")
    for key, allowance in customizations.items():
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


def _check_ignore_workspaces(repo: Repo, ctx: Context, parsed: dict[str, Any], res: CheckResult) -> None:
    """The declared globs must drop every non-production workspace and no production one — any spelling that does."""
    globs = parsed.get("ignoreWorkspaces")
    if not isinstance(globs, list) or not all(isinstance(glob, str) for glob in globs):
        res.fail(f'{PROD_CONFIG} "ignoreWorkspaces" must be a JSON array of workspace globs')
        return
    members = workspaces.ts_member_dirs(repo, ctx, ctx.paths(repo))
    production = {m for m in members if not m or ctx.config.source.is_production_file(f"{m}/{PACKAGE_JSON}")}
    dropped = {member for member in members if workspaces.matches_globs(member, globs)}
    kept = sorted(set(members) - dropped - production)
    if kept:
        res.fail(f'{PROD_CONFIG} "ignoreWorkspaces" leaves non-production workspace(s) in the graph: {", ".join(kept)}')
    dropped_production = sorted(dropped & production)
    if dropped_production:
        res.fail(f'{PROD_CONFIG} "ignoreWorkspaces" drops production workspace(s): {", ".join(dropped_production)}')


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

    required = {**base, "includeEntryExports": True}
    stray_keys = sorted(set(parsed) - set(required) - _PROD_EXTRA_KEYS)
    if stray_keys:
        res.fail(f"{PROD_CONFIG} has unexpected key(s): {', '.join(stray_keys)}")
    for key, expected in required.items():
        if parsed.get(key) != expected:
            res.fail(f'{PROD_CONFIG} must set "{key}": {json.dumps(expected)}')
    exclude = parsed.get("exclude")
    allowed_exclude = ctx.config.knip_prod_allowed_exclude
    if exclude is not None and exclude != allowed_exclude:
        res.fail(f'{PROD_CONFIG} "exclude" (if any) must be exactly {json.dumps(allowed_exclude)}')

    _check_ignore_workspaces(repo, ctx, parsed, res)
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
    try:
        _check_prod_config(repo, ctx, base, res)
    except yaml.YAMLError as exc:
        res.error(f"pnpm-workspace.yaml is not valid YAML: {exc}")
        return res

    if not res.problems:
        res.ok(_OK_MESSAGE)
    return res
