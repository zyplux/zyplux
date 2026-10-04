from __future__ import annotations

from typing import TYPE_CHECKING

from cerberus.architecture import list_dependencies, list_packages, run_package_policy
from cerberus.model import Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import CheckResult, Repo

ID = "dependency_direction"
SUMMARY = "Workspace dependency declarations respect configured ownership direction"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    packages = list_packages(repo, ctx)
    policy = ctx.config.architecture.dependencies

    def inspect(name: str, package: PackageInfo) -> list[str]:
        findings = []
        if name in policy:
            findings.extend(
                f"{name} cannot depend on {dependency}; this reverses the declared ownership direction"
                for dependency in sorted(list_dependencies(package.manifest) & packages.keys() - set(policy[name]))
            )
        return findings

    res = run_package_policy(repo, ctx, ID, inspect)
    for name, providers in policy.items():
        for package_name in (name, *providers):
            if package_name not in packages:
                res.fail(f"architecture.dependencies names unknown workspace package {package_name}")
    return res
