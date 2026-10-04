from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.architecture import Application, build_export_map, list_packages
from cerberus.model import CheckResult, Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import Repo

ID = "contract_keepers"
SUMMARY = "Each declared application scope has one keeper exposing only constants, contracts, and interfaces"
SCOPE = Scope.CONTENT
_SURFACES = {"./constants", "./contracts", "./interfaces"}


def _check_scope(
    scope: Application, packages: dict[str, PackageInfo], claimed: dict[str, str], res: CheckResult
) -> None:
    if scope.keeper not in scope.packages:
        res.fail(f"{scope.name}: keeper {scope.keeper} must belong to the application's packages")
    for name in scope.packages:
        if name not in packages:
            res.fail(f"{scope.name}: unknown workspace package {name}")
            continue
        previous = claimed.setdefault(name, scope.name)
        if previous != scope.name:
            res.fail(f"{name} belongs to multiple application scopes: {previous}, {scope.name}")
        surfaces = set(build_export_map(packages[name].manifest.get("exports"))) - {"./package.json"}
        if name == scope.keeper:
            if not surfaces or not surfaces <= _SURFACES:
                res.fail(f"{name}: keeper exposes only constants, contracts, and interfaces")
        elif surfaces and surfaces <= _SURFACES:
            res.fail(f"{scope.name}: {name} is a second contract-only package; the keeper is {scope.keeper}")


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    packages = list_packages(repo, ctx)
    scopes = ctx.config.architecture.applications
    if not scopes:
        res.skip("no application declares shared domain contracts")
        return res
    claimed: dict[str, str] = {}
    for scope in scopes:
        _check_scope(scope, packages, claimed, res)
    if not res.problems:
        res.ok("application scopes have one declared contract keeper")
    return res
