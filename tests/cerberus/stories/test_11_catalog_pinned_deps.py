from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding, RunCheckWithFiles

type RunCatalogDiscipline = Callable[[dict[str, str]], CheckResult]

CHECK_ID = "catalog_pinned_deps"

_CATALOG_WS_ROOT = '{"workspaces": ["packages/*"], "devDependencies": {"eslint": "catalog:"}}'
_CATALOG_NON_WS = '{"dependencies": {"eslint": "^9.0.0"}}'
_CATALOG_PINNED_PKG = '{"dependencies": {"@zyplux/util": "workspace:*", "zod": "catalog:"}}'
_CATALOG_RAW_PKG = '{"dependencies": {"zod": "^3.0.0"}}'
_CATALOG_VENDORED_PKG = '{"dependencies": {"left-pad": "^1.0.0"}}'


@pytest.fixture
def run_catalog_discipline(run_check_with_files: RunCheckWithFiles) -> RunCatalogDiscipline:
    return partial(run_check_with_files, CHECK_ID)


def test_11_1_1_skips_repos_with_no_package_json(
    run_catalog_discipline: RunCatalogDiscipline, skip: MakeFinding
) -> None:
    result = run_catalog_discipline({})
    assert result.findings == [skip("no package.json")]


def test_11_1_2_skips_repos_whose_package_json_is_not_a_workspace(
    run_catalog_discipline: RunCatalogDiscipline, skip: MakeFinding
) -> None:
    result = run_catalog_discipline({"package.json": _CATALOG_NON_WS})
    assert result.findings == [skip("not a workspace")]


def test_11_2_1_passes_when_every_dependency_pins_via_catalog_or_workspace(
    run_catalog_discipline: RunCatalogDiscipline, ok: MakeFinding
) -> None:
    result = run_catalog_discipline({"package.json": _CATALOG_WS_ROOT, "packages/a/package.json": _CATALOG_PINNED_PKG})
    assert result.findings == [ok("every dependency uses catalog: or workspace:")]


def test_11_2_2_fails_and_names_the_dependency_that_pins_a_raw_version(
    run_catalog_discipline: RunCatalogDiscipline, fail: MakeFinding
) -> None:
    result = run_catalog_discipline({"package.json": _CATALOG_WS_ROOT, "packages/a/package.json": _CATALOG_RAW_PKG})
    assert result.findings == [
        fail(
            "dependency not pinned via catalog:/workspace: — packages/a/package.json → dependencies.zod = '^3.0.0'",
        )
    ]


def test_11_2_3_treats_an_unparseable_manifest_as_declaring_no_dependencies(
    run_catalog_discipline: RunCatalogDiscipline, ok: MakeFinding
) -> None:
    result = run_catalog_discipline({"package.json": _CATALOG_WS_ROOT, "packages/a/package.json": "not json"})
    assert result.findings == [ok("every dependency uses catalog: or workspace:")]


def test_11_3_1_ignores_dependencies_declared_in_a_vendored_node_modules_package_json(
    run_catalog_discipline: RunCatalogDiscipline, ok: MakeFinding
) -> None:
    result = run_catalog_discipline({
        "package.json": _CATALOG_WS_ROOT,
        "node_modules/d/package.json": _CATALOG_VENDORED_PKG,
    })
    assert result.findings == [ok("every dependency uses catalog: or workspace:")]
