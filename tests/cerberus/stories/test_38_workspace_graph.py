from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from repository_fixture import ReportRepo


def find_node(report: str, label: str) -> str:
    node = re.search(rf'(ws_\d+)\["{re.escape(label)}"\]', report)
    assert node is not None, report
    return node.group(1)


def assert_edge(report: str, source: str, dependency: str, *, is_type: bool = False) -> None:
    start, end = find_node(report, source), find_node(report, dependency)
    arrow = "-.->" if is_type else "-->"
    assert f"{start} {start}__{end}@{arrow} {end}" in report


@pytest.mark.parametrize("field", ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"])
def test_38_1_1_draws_declared_dependencies_for_registered_workspaces(report_repo: ReportRepo, field: str) -> None:
    report_repo.seed_workspaces()
    report_repo.write_package(
        "apps/server", name="@acme/server", version="1.0.0", **{field: {"@acme/one": "workspace:*", "external": "1"}}
    )
    report_repo.write_package("doubles", name="@acme/doubles", version="1.0.0")
    report_repo.write_package("tests/server", name="@acme/server-tests", version="1.0.0")
    report_repo.write_package("unregistered", name="@acme/unknown", version="1.0.0")
    result = report_repo.invoke("workspace-graph")
    assert result.exit_code == 0, result.output
    report = report_repo.read("WORKSPACE_GRAPH.md")
    assert_edge(report, "server", "one")
    assert "stroke-width:2px" in report
    assert all(f'["{name}"]' not in report for name in ("external", "doubles", "server-tests", "unknown"))


@pytest.mark.parametrize(
    ("source", "is_type"),
    [
        ('import type { Item } from "@acme/one/subpath";', True),
        ('import { type Item } from "@acme/one";', True),
        ('export type { Item } from "@acme/one";', True),
        ('export { type Item } from "@acme/one";', True),
        ('import Item, { type Other } from "@acme/one";', False),
        ('import { type Item, create } from "@acme/one";', False),
        ('const dependency = import("@acme/one");', False),
        ('const dependency = require("@acme/one");', False),
        ('// import type { Item } from "@acme/one";', False),
    ],
)
def test_38_1_2_distinguishes_type_imports_from_runtime_dependencies(
    report_repo: ReportRepo, source: str, *, is_type: bool
) -> None:
    report_repo.seed_workspaces()
    report_repo.write_package(
        "apps/server", name="@acme/server", version="1.0.0", dependencies={"@acme/one": "workspace:*"}
    )
    report_repo.write("apps/server/src/index.ts", source)
    report_repo.write("apps/server/src/index.test.ts", 'import "@acme/one";')
    result = report_repo.invoke("workspace-graph")
    assert result.exit_code == 0, result.output
    assert_edge(report_repo.read("WORKSPACE_GRAPH.md"), "server", "one", is_type=is_type)


def test_38_1_3_prefers_value_imports_seen_in_another_source_file(report_repo: ReportRepo) -> None:
    report_repo.seed_workspaces()
    report_repo.write_package(
        "apps/server", name="@acme/server", version="1.0.0", dependencies={"@acme/one": "workspace:*"}
    )
    report_repo.write("apps/server/src/a.ts", 'import type { Item } from "@acme/one";')
    report_repo.write("apps/server/src/b.ts", 'export { create } from "@acme/one";')
    assert report_repo.invoke("workspace-graph").exit_code == 0
    assert_edge(report_repo.read("WORKSPACE_GRAPH.md"), "server", "one")


def test_38_1_4_includes_python_projects_and_merges_dual_manifests(report_repo: ReportRepo) -> None:
    report_repo.seed_workspaces()
    report_repo.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["infra/*", "tools/*"]\n')
    report_repo.write(
        "infra/service/pyproject.toml", '[project]\nname = "service"\nversion = "1"\ndependencies = ["Acme_Util>=1"]\n'
    )
    report_repo.write_package("infra/service", name="@acme/service", version="1.0.0")
    report_repo.write("tools/util/pyproject.toml", '[project]\nname = "acme-util"\nversion = "1"\n')
    result = report_repo.invoke("workspace-graph")
    assert result.exit_code == 0, result.output
    report = report_repo.read("WORKSPACE_GRAPH.md")
    assert report.count('["service"]') == 1
    assert_edge(report, "service", "acme-util")
    assert '["infra"]' in report
    assert '["tools"]' in report


@pytest.mark.parametrize(
    "declaration",
    [
        '[project.optional-dependencies]\nextra = ["acme-util"]\n',
        '[dependency-groups]\ndev = ["acme-util", {include-group = "lint"}]\n',
    ],
)
def test_38_1_5_includes_optional_and_development_python_dependencies(
    report_repo: ReportRepo, declaration: str
) -> None:
    report_repo.seed_workspaces()
    report_repo.write("infra/service/pyproject.toml", '[project]\nname = "service"\nversion = "1"\n' + declaration)
    report_repo.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["infra/*", "tools/*"]\n')
    report_repo.write("tools/util/pyproject.toml", '[project]\nname = "acme-util"\nversion = "1"\n')
    assert report_repo.invoke("workspace-graph").exit_code == 0
    assert_edge(report_repo.read("WORKSPACE_GRAPH.md"), "service", "acme-util")


def test_38_1_6_includes_the_root_python_project_with_workspace_members(report_repo: ReportRepo) -> None:
    report_repo.write(
        "pyproject.toml",
        '[project]\nname = "root-project"\nversion = "1"\ndependencies = ["child"]\n'
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
    )
    report_repo.write(
        "packages/child/pyproject.toml",
        '[project]\nname = "child"\nversion = "1"\ndependencies = ["root-project"]\n',
    )
    report_repo.write("packages/unrelated/pyproject.toml", '[project]\nname = "unrelated"\nversion = "1"\n')
    assert report_repo.invoke("workspace-graph").exit_code == 0
    report = report_repo.read("WORKSPACE_GRAPH.md")
    assert_edge(report, "root-project", "child")
    assert_edge(report, "child", "root-project")


def test_38_1_7_includes_the_root_npm_project_with_workspace_members(report_repo: ReportRepo) -> None:
    report_repo.seed_workspaces()
    report_repo.write_package("", name="root-project", version="1.0.0", devDependencies={"@acme/one": "workspace:*"})
    report_repo.write_package(
        "packages/one", name="@acme/one", version="1.0.0", dependencies={"root-project": "workspace:*"}
    )
    assert report_repo.invoke("workspace-graph").exit_code == 0
    report = report_repo.read("WORKSPACE_GRAPH.md")
    assert_edge(report, "root-project", "one")
    assert_edge(report, "one", "root-project")


def test_38_2_1_lists_frequent_foundations_and_keeps_reruns_deterministic(report_repo: ReportRepo) -> None:
    report_repo.seed_workspaces()
    for name in ("alpha", "beta", "gamma"):
        report_repo.write_package(
            f"apps/{name}", name=f"@acme/{name}", version="1.0.0", dependencies={"@acme/one": "workspace:*"}
        )
    assert report_repo.invoke("workspace-graph").exit_code == 0
    first = report_repo.read("WORKSPACE_GRAPH.md")
    assert "## Foundations" in first
    assert "- **`one`** ← `alpha`, `beta`, `gamma`" in first
    assert ":::foundation" in first
    assert report_repo.invoke("workspace-graph").exit_code == 0
    assert report_repo.read("WORKSPACE_GRAPH.md") == first


def test_38_2_2_respects_exclusions_and_root_paths(report_repo: ReportRepo, monkeypatch: pytest.MonkeyPatch) -> None:
    report_repo.seed_workspaces()
    report_repo.write("pnpm-workspace.yaml", "packages: ['packages/*', '!packages/two/**']\n")
    nested = report_repo.root / "packages/one"
    monkeypatch.chdir(nested)
    result = report_repo.invoke("workspace-graph")
    assert result.exit_code == 0, result.output
    assert '["two"]' not in report_repo.read("WORKSPACE_GRAPH.md")
    assert not (nested / "WORKSPACE_GRAPH.md").exists()


def test_38_2_3_supports_standalone_and_empty_repositories(report_repo: ReportRepo) -> None:
    assert report_repo.invoke("workspace-graph").exit_code == 0
    assert "No workspace projects are declared" in report_repo.read("WORKSPACE_GRAPH.md")
    report_repo.write_package("", name="standalone", version="1.0.0")
    report_repo.write("pyproject.toml", '[project]\nname = "standalone"\nversion = "1"\n')
    assert report_repo.invoke("workspace-graph").exit_code == 0
    assert report_repo.read("WORKSPACE_GRAPH.md").count('["standalone"]') == 1


def test_38_3_1_reports_invalid_manifests_without_overwriting_the_report(report_repo: ReportRepo) -> None:
    report_repo.seed_workspaces()
    report_repo.write("packages/one/package.json", "{invalid")
    report_repo.write("WORKSPACE_GRAPH.md", "previous report")
    result = report_repo.invoke("workspace-graph")
    assert result.exit_code == 1
    assert "Invalid JSON" in result.output
    assert report_repo.read("WORKSPACE_GRAPH.md") == "previous report"
