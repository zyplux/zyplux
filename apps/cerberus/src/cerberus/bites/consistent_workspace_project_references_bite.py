from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from cerberus.architecture import list_dependencies, list_packages
from cerberus.model import CheckResult, Scope
from cerberus.ts_syntax import parse_jsonc

if TYPE_CHECKING:
    from cerberus.context import Context
    from cerberus.model import Repo

ID = "consistent_workspace_project_references"
SUMMARY = "Workspace TypeScript projects reference each compiled workspace dependency once"
SCOPE = Scope.CONTENT


def _list_references(
    path: str,
    entries: list[dict[str, str]],
    directories: dict[str, str],
    paths: set[str],
    res: CheckResult,
) -> list[str]:
    references = []
    for entry in entries:
        target = posixpath.normpath(posixpath.join(posixpath.dirname(path), entry["path"]))
        config_path = target if target.endswith(".json") else posixpath.join(target, "tsconfig.json")
        provider = directories.get(posixpath.dirname(config_path))
        if provider is None or config_path not in paths:
            res.fail(f"{path}: reference {entry['path']} is not a workspace TypeScript project")
        else:
            references.append(provider)
    return references


def run(repo: Repo, ctx: Context) -> CheckResult:
    res = CheckResult(ID, repo.name)
    projects = {}
    for name, package in list_packages(repo, ctx).items():
        path = posixpath.join(package.directory, "tsconfig.json")
        content = ctx.file(repo, path)
        if content is not None:
            projects[name] = (package, path, parse_jsonc(content))
    if not projects:
        res.skip("no workspace TypeScript projects")
        return res
    directories = {package.directory: name for name, (package, _, _) in projects.items()}
    for package, path, config in projects.values():
        references = _list_references(path, config.get("references", []), directories, set(ctx.paths(repo)), res)
        if len(set(references)) != len(references):
            res.fail(f"{path}: duplicate project references")
        dependencies = list_dependencies(package.manifest) & projects.keys()
        for missing in sorted(dependencies - set(references)):
            res.fail(f"{path}: missing project reference to {missing}")
        for extra in sorted(set(references) - dependencies):
            res.fail(f"{path}: reference to {extra} has no workspace dependency")
    if not res.problems:
        res.ok("TypeScript project references agree with workspace dependencies")
    return res
