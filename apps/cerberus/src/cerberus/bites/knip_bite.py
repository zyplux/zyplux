"""Validate Knip configuration and enforce production export and workspace scope."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import yaml
from airlock.targets import parse_manifest

from cerberus.model import CheckResult, Scope
from cerberus.toolchain.source_languages import has_source
from cerberus.workspaces import workspace_members

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
_RELEASE_TARGETS = "airlock_targets.toml"
_PROD_EXTRA_KEYS = frozenset({"$schema", "workspaces", "exclude", "ignoreWorkspaces"})
_OK_MESSAGE = (
    "knip.json (if any) stays within the shared allowances; knip.prod.json exactly exempts every published npm target"
)


def _without_schema(parsed: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in parsed.items() if key != "$schema"}


def _npm_workspace_dirs(manifest: str) -> set[str]:
    try:
        specs = parse_manifest(manifest)
    except ValueError:
        return set()
    return {
        spec.manifest[: -len(f"/{PACKAGE_JSON}")]
        for spec in specs
        if spec.kind == "npm" and spec.manifest.endswith(f"/{PACKAGE_JSON}")
    }


def _check_no_inline_key(manifest: dict[str, Any], res: CheckResult) -> None:
    if "knip" in manifest:
        res.fail(f'{PACKAGE_JSON} must not have a "knip" key; move its content to a standalone {BASE_CONFIG}')


def _check_customizations(parsed: dict[str, Any], path: str, ctx: Context, res: CheckResult) -> None:
    customizations = ctx.config.knip_allowed_customizations
    for key, allowance in customizations.items():
        names = parsed.get(key)
        if names is None:
            continue
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            res.fail(f'{path} "{key}" must be a JSON array of strings')
            continue
        outside = sorted(set(names) - allowance)
        if outside:
            res.fail(f"{path} {key} allows only {', '.join(sorted(allowance))}; not allowed: {', '.join(outside)}")


def _check_base_config(repo: Repo, ctx: Context, res: CheckResult) -> None:
    content = ctx.file(repo, BASE_CONFIG)
    if content is None:
        return
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        res.error(f"could not parse {BASE_CONFIG}: {exc}")
        return
    if not isinstance(parsed, dict):
        res.error(f"{BASE_CONFIG} must be a JSON object")
        return
    base = _without_schema(parsed)
    customizations = ctx.config.knip_allowed_customizations
    stray_keys = sorted(set(base) - set(customizations))
    if stray_keys:
        allowed_keys = ", ".join(f'"{key}"' for key in customizations)
        res.fail(f"{BASE_CONFIG} may only customize {allowed_keys}; unexpected key(s): {', '.join(stray_keys)}")
    _check_customizations(base, BASE_CONFIG, ctx, res)


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
    members = workspace_members.ts_member_dirs(repo, ctx, ctx.paths(repo))
    production = {m for m in members if not m or ctx.config.source_oracle.is_production_file(f"{m}/{PACKAGE_JSON}")}
    dropped = {member for member in members if workspace_members.matches_globs(member, globs)}
    kept = sorted(set(members) - dropped - production)
    dropped_production = sorted(dropped & production)
    if ctx.fix and (kept or dropped_production):
        parsed["ignoreWorkspaces"] = sorted(set(members) - production)
        ctx.write_file(repo, PROD_CONFIG, json.dumps(parsed, indent=2) + "\n")
        return
    if kept:
        res.fail(f'{PROD_CONFIG} "ignoreWorkspaces" leaves non-production workspace(s) in the graph: {", ".join(kept)}')
    if dropped_production:
        res.fail(f'{PROD_CONFIG} "ignoreWorkspaces" drops production workspace(s): {", ".join(dropped_production)}')


def _check_prod_config(repo: Repo, ctx: Context, res: CheckResult) -> None:
    content = ctx.file(repo, PROD_CONFIG)
    if content is None:
        if has_source(repo, ctx, "typescript"):
            res.fail(f"no {PROD_CONFIG} at repo root — needed to catch dead/test-only exports")
        else:
            res.skip(f"no TypeScript source or {PROD_CONFIG}")
        return
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        res.error(f"could not parse {PROD_CONFIG}: {exc}")
        return
    if not isinstance(parsed, dict):
        res.error(f"{PROD_CONFIG} must be a JSON object")
        return

    required = {"includeEntryExports": True}
    stray_keys = sorted(set(parsed) - set(required) - _PROD_EXTRA_KEYS - set(ctx.config.knip_allowed_customizations))
    if stray_keys:
        res.fail(f"{PROD_CONFIG} has unexpected key(s): {', '.join(stray_keys)}")
    for key, expected in required.items():
        if parsed.get(key) != expected:
            res.fail(f'{PROD_CONFIG} must set "{key}": {json.dumps(expected)}')
    exclude = parsed.get("exclude")
    allowed_exclude = ctx.config.knip_prod_allowed_exclude
    if exclude is not None and exclude != allowed_exclude:
        res.fail(f'{PROD_CONFIG} "exclude" (if any) must be exactly {json.dumps(allowed_exclude)}')

    _check_customizations(parsed, PROD_CONFIG, ctx, res)
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
    _check_base_config(repo, ctx, res)
    try:
        _check_prod_config(repo, ctx, res)
    except yaml.YAMLError as exc:
        res.error(f"pnpm-workspace.yaml is not valid YAML: {exc}")
        return res

    if not res.findings:
        res.ok(_OK_MESSAGE)
    return res
