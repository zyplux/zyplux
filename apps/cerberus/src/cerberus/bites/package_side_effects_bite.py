from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from cerberus.architecture import is_library, run_package_policy
from cerberus.graph.parse import parse_typescript
from cerberus.model import Scope

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.graph.resolve_ts import PackageInfo
    from cerberus.model import CheckResult, Repo

ID = "package_side_effects"
SUMMARY = "Libraries declare side effects and preserve modules that execute registration or initialization"
SCOPE = Scope.CONTENT


def run(repo: Repo, ctx: Context) -> CheckResult:
    def inspect(_name: str, package: PackageInfo) -> list[str]:
        if not is_library(package):
            return []
        metadata = package.manifest.get("sideEffects")
        if (
            metadata is not False
            and metadata is not True
            and not (isinstance(metadata, list) and all(isinstance(entry, str) for entry in metadata))
        ):
            return ["declare sideEffects as false, true, or module patterns"]
        if metadata is True:
            return []
        findings = []
        prefix = f"{package.directory}/src/"
        for path in ctx.paths(repo):
            if not path.startswith(prefix) or PurePosixPath(path).suffix not in {".ts", ".tsx"}:
                continue
            content = ctx.file(repo, path)
            if content is None:
                continue
            tree = parse_typescript(path, content)
            if not any(node.type == "expression_statement" for node in tree.root_node.named_children):
                continue
            built = "dist/" + path.removeprefix(prefix).rsplit(".", 1)[0] + ".js"
            if metadata is False or not any(
                PurePosixPath(built).full_match(pattern.removeprefix("./")) for pattern in metadata
            ):
                findings.append(f"{path} executes a top-level statement; list {built} in sideEffects")
        return findings

    return run_package_policy(repo, ctx, ID, inspect)
