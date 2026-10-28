from __future__ import annotations

import colorsys
import math
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from airlock.contracts import NpmPackage
from airlock.proc import find_root
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from pydantic import BaseModel, Field

from cerberus import config, context, workspaces
from cerberus.graph.parse import parse_typescript

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node

    from cerberus.context import Context
    from cerberus.model import Repo

REPORT_NAME = "WORKSPACE_GRAPH.md"
FOUNDATION_RATIO = 0.4
TS_SUFFIXES = {".ts", ".tsx", ".mts", ".cts"}


class NpmManifest(NpmPackage):
    name: str
    dev_dependencies: dict[str, str] = Field(default_factory=dict, alias="devDependencies")
    peer_dependencies: dict[str, str] = Field(default_factory=dict, alias="peerDependencies")


class PythonProject(BaseModel):
    name: str
    dependencies: list[str] = Field(default_factory=list)
    optional_dependencies: dict[str, list[str]] = Field(default_factory=dict, alias="optional-dependencies")


class PythonManifest(BaseModel):
    project: PythonProject | None = None
    dependency_groups: dict[str, list[str | dict[str, str]]] = Field(default_factory=dict, alias="dependency-groups")


@dataclass
class Workspace:
    directory: str
    label: str
    dependencies: set[str] = field(default_factory=set)
    type_dependencies: set[str] = field(default_factory=set)

    @property
    def group(self) -> str:
        return self.directory.split("/", 1)[0] if self.directory else "root"


def walk_nodes(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from walk_nodes(child)


def read_import(node: Node) -> tuple[str, bool] | None:
    source = node.child_by_field_name("source")
    if source is not None and node.type in {"import_statement", "export_statement"}:
        specifiers = [child for child in walk_nodes(node) if child.type in {"import_specifier", "export_specifier"}]
        clause = next((child for child in node.children if child.type == "import_clause"), None)
        has_default = clause is not None and any(child.type == "identifier" for child in clause.children)
        is_type = any(child.type == "type" for child in node.children) or (
            bool(specifiers)
            and not has_default
            and all(any(child.type == "type" for child in specifier.children) for specifier in specifiers)
        )
        return (source.text or b"").decode("utf-8")[1:-1], is_type
    if node.type == "call_expression":
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is not None and function.text in {b"import", b"require"} and arguments is not None:
            literal = next((child for child in arguments.named_children if child.type == "string"), None)
            if literal is not None:
                return (literal.text or b"").decode("utf-8")[1:-1], False
    return None


def load_type_dependencies(repo: Repo, ctx: Context, npm: dict[str, Workspace]) -> None:
    imports: dict[str, dict[str, set[bool]]] = {}
    directories = sorted({workspace.directory for workspace in npm.values()}, key=len, reverse=True)
    source_scope = ctx.config.source
    for path in ctx.paths(repo):
        if Path(path).suffix not in TS_SUFFIXES or source_scope.is_test_file(path):
            continue
        owner = next(
            (directory for directory in directories if not directory or path.startswith(f"{directory}/")), None
        )
        content = ctx.file(repo, path)
        if owner is None or content is None:
            continue
        for node in walk_nodes(parse_typescript(path, content).root_node):
            imported = read_import(node)
            if imported is None:
                continue
            specifier, is_type = imported
            dependency = next((name for name in npm if specifier == name or specifier.startswith(f"{name}/")), None)
            if dependency is not None:
                imports.setdefault(owner, {}).setdefault(npm[dependency].directory, set()).add(is_type)
    for workspace in npm.values():
        workspace.type_dependencies = {
            dependency for dependency, kinds in imports.get(workspace.directory, {}).items() if kinds == {True}
        }


def load_workspaces(repo: Repo, ctx: Context) -> list[Workspace]:
    paths = ctx.paths(repo)
    npm: dict[str, Workspace] = {}
    python: dict[str, Workspace] = {}
    members: dict[str, Workspace] = {}
    npm_manifests: dict[str, NpmManifest] = {}
    python_manifests: dict[str, PythonManifest] = {}
    for directory in workspaces.list_source_members(workspaces.ts_member_dirs(repo, ctx, paths), ctx.config.source):
        manifest = NpmManifest.model_validate_json(ctx.file(repo, f"{directory}/package.json".lstrip("/")) or "{}")
        workspace = Workspace(directory, manifest.name.rsplit("/", 1)[-1])
        members[directory] = npm[manifest.name] = workspace
        npm_manifests[directory] = manifest
    globs = workspaces.uv_member_globs(repo, ctx)
    directories = workspaces.member_dirs(paths, globs, "pyproject.toml") if globs else [""]
    for directory in workspaces.list_source_members(directories, ctx.config.source):
        manifest = PythonManifest.model_validate(
            tomllib.loads(ctx.file(repo, f"{directory}/pyproject.toml".lstrip("/")) or "")
        )
        if manifest.project is not None:
            workspace = members.setdefault(directory, Workspace(directory, manifest.project.name))
            python[canonicalize_name(manifest.project.name)] = workspace
            python_manifests[directory] = manifest
    for directory, manifest in npm_manifests.items():
        members[directory].dependencies.update(
            npm[name].directory
            for dependencies in (
                manifest.dependencies,
                manifest.dev_dependencies,
                manifest.optional_dependencies,
                manifest.peer_dependencies,
            )
            for name in dependencies
            if name in npm
        )
    for directory, manifest in python_manifests.items():
        project = manifest.project
        if project is None:
            continue
        requirements = [
            *project.dependencies,
            *(requirement for group in project.optional_dependencies.values() for requirement in group),
            *(
                requirement
                for group in manifest.dependency_groups.values()
                for requirement in group
                if isinstance(requirement, str)
            ),
        ]
        for requirement in requirements:
            name = canonicalize_name(Requirement(requirement).name)
            if name in python:
                members[directory].dependencies.add(python[name].directory)
    load_type_dependencies(repo, ctx, npm)
    for workspace in members.values():
        workspace.dependencies.discard(workspace.directory)
    return sorted(members.values(), key=lambda workspace: workspace.directory)


def calc_edge_color(index: int, count: int) -> str:
    hue = ((210 + 360 * index / count) % 360) / 360
    channels = colorsys.hls_to_rgb(hue, 0.65, 0.7)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in channels)


def quote_label(label: str) -> str:
    return label.replace("&", "&amp;").replace('"', "#quot;").replace("<", "&lt;").replace("]", "#93;")


def build_foundation_section(members: list[Workspace], foundations: set[str]) -> list[str]:
    if not foundations:
        return []
    threshold = math.ceil(len(members) * FOUNDATION_RATIO)
    lines = ["## Foundations", "", f"Imported by at least 40% of workspaces ({threshold}/{len(members)}):", ""]
    for workspace in members:
        if workspace.directory not in foundations:
            continue
        importers = [
            f"`{importer.label}`{' (type-only)' if workspace.directory in importer.type_dependencies else ''}"
            for importer in members
            if workspace.directory in importer.dependencies
        ]
        lines.append(f"- **`{workspace.label}`** ← {', '.join(importers)}")
    return [*lines, ""]


def build_report(members: list[Workspace]) -> str:
    if not members:
        return "# Workspace Dependency Graph\n\nNo workspace projects are declared.\n"
    ids = {workspace.directory: f"ws_{index}" for index, workspace in enumerate(members)}
    in_degrees = Counter(dependency for workspace in members for dependency in workspace.dependencies)
    foundations = {directory for directory, count in in_degrees.items() if count >= len(members) * FOUNDATION_RATIO}
    groups = sorted({workspace.group for workspace in members})
    lines = [
        "# Workspace Dependency Graph",
        "",
        "*Which workspace projects depend on each other?*",
        "",
        "```mermaid",
        "---",
        "config:",
        "  theme: dark",
        "  layout: elk",
        "---",
        "flowchart LR",
        "    subgraph workspaces",
    ]
    for index, group in enumerate(groups):
        lines.append(f'        subgraph group_{index}["{quote_label(group)}"]')
        for workspace in members:
            if workspace.group == group:
                style = ":::foundation" if workspace.directory in foundations else ""
                lines.append(f'            {ids[workspace.directory]}["{quote_label(workspace.label)}"]{style}')
        lines.append("        end")
    lines.append("    end")
    apps = [workspace for workspace in members if workspace.group == "apps"]
    for workspace in members:
        edge_ids = []
        for dependency in sorted(workspace.dependencies - foundations):
            edge_id = f"{ids[workspace.directory]}__{ids[dependency]}"
            arrow = "-.->" if dependency in workspace.type_dependencies else "-->"
            lines.append(f"    {ids[workspace.directory]} {edge_id}@{arrow} {ids[dependency]}")
            edge_ids.append(edge_id)
        if edge_ids and workspace in apps:
            style = f"{ids[workspace.directory]}_edges"
            color = calc_edge_color(apps.index(workspace), len(apps))
            lines.extend([
                f"    classDef {style} stroke:{color},stroke-width:2px",
                f"    class {','.join(edge_ids)} {style}",
            ])
    lines.extend([
        "    classDef foundation fill:#2b2b2b,stroke:#888,stroke-dasharray:5 5",
        "    style workspaces fill:transparent,stroke:none",
        "```",
        "",
        "Solid arrows are declared workspace dependencies; dashed arrows have only type imports in TypeScript source.",
        "",
    ])
    lines.extend(build_foundation_section(members, foundations))
    lines.extend(["Generate with `uv run cerberus workspace-graph`.", ""])
    return "\n".join(lines)


def write_report(path: Path) -> Path:
    root = find_root(path)
    ctx = context.local_context(config.load(repo_root=root), root)
    members = load_workspaces(ctx.repos()[0], ctx)
    destination = root / REPORT_NAME
    destination.write_text(build_report(members), encoding="utf-8")
    return destination
