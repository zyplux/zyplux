from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from seam_fixtures import RunCheckWithFiles


def _workspace(manifests: dict[str, dict[str, object]]) -> dict[str, str]:
    return {
        "package.json": '{"name":"sample"}',
        "pnpm-workspace.yaml": "packages: [packages/*, apps/*]",
        **{
            f"packages/{name}/package.json": json.dumps({"name": name, **manifest})
            for name, manifest in manifests.items()
        },
    }


@pytest.mark.parametrize(
    "exports",
    [
        "./src/index.ts",
        {".": "./src/index.ts"},
        {"./api": {"import": "./src/api.ts", "types": "./dist/api.d.ts"}},
        {"./assets/*": "./assets/*", "./api": "./src/api.ts"},
        {"./private": None, "./api": "./src/api.ts"},
    ],
)
def test_34_1_1_accepts_library_export_families_and_conditional_or_asset_entries(
    run_check_with_files: RunCheckWithFiles, exports: object
) -> None:
    assert not run_check_with_files("package_exports", _workspace({"library": {"exports": exports}})).problems


@pytest.mark.parametrize(
    "manifest",
    [
        {"exports": {".": "./src/index.ts", "./api": "./src/api.ts"}},
        {"exports": {"./api": "./src/helpers.ts"}},
        {"exports": {"./api": "./src/api.ts"}, "publishConfig": {"exports": {".": "./dist/index.js"}}},
    ],
)
def test_34_1_2_rejects_mixed_exports_misnamed_entries_and_published_key_drift(
    run_check_with_files: RunCheckWithFiles, manifest: dict[str, object]
) -> None:
    assert run_check_with_files("package_exports", _workspace({"library": manifest})).problems


def test_34_1_3_preserves_framework_application_roots_and_binary_only_apps(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "package.json": '{"name":"sample"}',
        "pnpm-workspace.yaml": "packages: [apps/*]",
        "apps/web/package.json": '{"name":"web","exports":{".":"./src/router.tsx"}}',
        "apps/cli/package.json": '{"name":"cli","bin":{"cli":"./src/cli.ts"}}',
    }
    assert not run_check_with_files("package_exports", files).problems


_SCOPE = '[[architecture.applications]]\nname="application"\nkeeper="domain"\npackages=["domain","implementation"]\n'


def test_34_2_1_checks_one_keeper_within_each_independent_application_scope(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    manifests: dict[str, dict[str, object]] = {
        "domain": {"exports": {"./contracts": "./src/contracts.ts"}},
        "implementation": {"exports": {".": "./src/index.ts", "./contracts": "./src/contracts.ts"}},
        "other": {"exports": {"./contracts": "./src/contracts.ts"}},
    }
    assert not run_check_with_files("contract_keepers", _workspace(manifests), _SCOPE).problems


@pytest.mark.parametrize(
    ("keeper", "implementation"),
    [
        ({".": "./src/index.ts"}, {}),
        ({"./contracts": "./src/contracts.ts"}, {"./interfaces": "./src/interfaces.ts"}),
        ({}, {}),
    ],
)
def test_34_2_2_rejects_invalid_keeper_surfaces_and_second_contract_only_packages(
    run_check_with_files: RunCheckWithFiles, keeper: dict[str, str], implementation: dict[str, str]
) -> None:
    assert run_check_with_files(
        "contract_keepers",
        _workspace({"domain": {"exports": keeper}, "implementation": {"exports": implementation}}),
        _SCOPE,
    ).problems


@pytest.mark.parametrize(
    "scope",
    [
        _SCOPE.replace('keeper="domain"', 'keeper="missing"'),
        _SCOPE.replace('"implementation"', '"missing"'),
        _SCOPE + _SCOPE.replace('name="application"', 'name="other"'),
    ],
)
def test_34_2_3_rejects_unknown_packages_and_overlapping_application_scopes(
    run_check_with_files: RunCheckWithFiles, scope: str
) -> None:
    assert run_check_with_files(
        "contract_keepers",
        _workspace({"domain": {"exports": {"./contracts": "./src/contracts.ts"}}, "implementation": {}}),
        scope,
    ).problems


@pytest.mark.parametrize("category", ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"])
def test_34_3_1_dependency_direction_checks_each_manifest_dependency_category(
    run_check_with_files: RunCheckWithFiles, category: str
) -> None:
    files = _workspace({"foundation": {category: {"implementation": "workspace:*"}}, "implementation": {}})
    assert run_check_with_files("dependency_direction", files, "[architecture.dependencies]\nfoundation=[]").problems
    assert not run_check_with_files(
        "dependency_direction", files, '[architecture.dependencies]\nfoundation=["implementation"]'
    ).problems


def test_34_3_2_rejects_unknown_dependency_policy_packages(run_check_with_files: RunCheckWithFiles) -> None:
    assert run_check_with_files(
        "dependency_direction", _workspace({"foundation": {}}), '[architecture.dependencies]\nfoundation=["missing"]'
    ).problems


@pytest.mark.parametrize(
    ("references", "has_failure"),
    [
        ([], True),
        ([{"path": "../provider"}], False),
        ([{"path": "../provider/tsconfig.json"}], False),
        ([{"path": "../provider"}, {"path": "../provider"}], True),
        ([{"path": "../missing"}], True),
        ([{"path": "../provider/missing.json"}], True),
    ],
)
def test_34_4_1_project_references_match_compiled_dependencies_once(
    run_check_with_files: RunCheckWithFiles, references: list[dict[str, str]], *, has_failure: bool
) -> None:
    files = _workspace({"consumer": {"dependencies": {"provider": "workspace:*"}}, "provider": {}})
    files.update({
        "packages/provider/tsconfig.json": '{"compilerOptions":{"composite":true}}',
        "packages/consumer/tsconfig.json": json.dumps({
            "compilerOptions": {"composite": True},
            "references": references,
        }),
    })
    assert bool(run_check_with_files("project_references", files).problems) is has_failure


def test_34_4_2_project_references_resolve_jsonc_and_inherited_workspace_configs(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = _workspace({
        "consumer": {"devDependencies": {"configuration": "workspace:*"}},
        "configuration": {"exports": {"./base.json": "./base.json"}},
    })
    files.update({
        "packages/configuration/base.json": '{ /* build options */ "compilerOptions": {"composite": true,},}',
        "packages/consumer/tsconfig.json": '{"extends":"configuration/base.json", "references": [],}',
    })
    assert not run_check_with_files("project_references", files).problems


@pytest.mark.parametrize(
    ("side_effects", "has_failure"),
    [(False, True), (True, False), (["./dist/register.js"], False), (["./dist/other.js"], True), (None, True)],
)
@pytest.mark.parametrize(
    "source",
    [
        "registerMatchers();",
        "const registerMatchers = () => { expect.extend({}); return {}; }; export const matchers = registerMatchers();",
        "function registerMatchers() { expect.extend({}); return {}; } export const matchers = registerMatchers();",
        (
            "const register = () => { expect.extend({}); }; "
            "const initialize = () => register(); export const ready = initialize();"
        ),
    ],
)
def test_34_5_1_side_effect_metadata_preserves_registration_modules(
    run_check_with_files: RunCheckWithFiles, side_effects: object, source: str, *, has_failure: bool
) -> None:
    files = _workspace({"library": {"exports": {"./register": "./src/register.ts"}, "sideEffects": side_effects}})
    files["packages/library/src/register.ts"] = source
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_failure


@pytest.mark.parametrize(
    "source",
    [
        'export * from "./api.ts";',
        "export const buildSchema = () => { const schema = z.object({}); return schema; };",
        "export function register() { expect.extend({}); }",
        'export class Reporter { record() { console.log("recording"); } }',
        "export const schema = z.object({});",
        "const collect = (depth = 0) => depth > 0 ? collect(depth - 1) : []; export const entries = collect();",
    ],
)
def test_34_5_2_pure_libraries_may_declare_no_side_effects(
    run_check_with_files: RunCheckWithFiles, source: str
) -> None:
    files = _workspace({"library": {"exports": {".": "./src/index.ts"}, "sideEffects": False}})
    files["packages/library/src/index.ts"] = source
    assert not run_check_with_files("package_side_effects", files).problems


@pytest.mark.parametrize(
    ("source", "has_failure"),
    [
        ('import "node:fs";', True),
        ('import type { Stats } from "node:fs";', False),
        ('export type { Stats } from "node:fs";', False),
        ('type Stats = import("node:fs").Stats;', False),
        ('const read = (): typeof import("node:fs") => ({});', False),
        ('const load = () => import("node:fs/promises");', True),
        ('const text = "import node:fs"; // import "node:fs"', False),
    ],
)
def test_34_6_1_workers_follow_runtime_imports_and_ignore_type_edges_or_text(
    run_check_with_files: RunCheckWithFiles, source: str, *, has_failure: bool
) -> None:
    files = _workspace({"shared": {"exports": {"./api": {"import": "./src/api.ts", "types": "./src/types.ts"}}}})
    files.update({
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "shared/api";',
        "packages/shared/src/api.ts": source,
        "packages/shared/src/types.ts": 'import "node:fs";',
    })
    assert bool(run_check_with_files("worker_runtime", files).problems) is has_failure


def test_34_6_2_workers_resolve_local_aliases_and_package_import_maps(run_check_with_files: RunCheckWithFiles) -> None:
    files = _workspace({
        "shared": {"imports": {"#internal": "./src/internal.ts"}, "exports": {"./api": "./src/api.ts"}}
    })
    files.update({
        "apps/worker/wrangler.toml": 'main="src/index.ts"',
        "apps/worker/tsconfig.json": '{"compilerOptions":{"paths":{"@/*":["./src/*"]}}}',
        "apps/worker/src/index.ts": 'import "@/entry";',
        "apps/worker/src/entry.ts": 'import "shared/api";',
        "packages/shared/src/api.ts": 'import "#internal";',
        "packages/shared/src/internal.ts": 'import "node:fs";',
    })
    assert run_check_with_files("worker_runtime", files).problems


def test_34_6_3_worker_scan_reports_missing_first_party_entries_and_visible_external_gaps(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "third-party"; const load = (name: string) => import(name);',
    }
    result = run_check_with_files("worker_runtime", files)
    assert not result.problems
    assert result.verbose_lines == [
        "apps/worker/src/index.ts:1: computed dynamic import cannot be resolved statically",
        "third-party runtime third-party is outside the first-party graph",
    ]
    files["apps/worker/src/index.ts"] = 'import "./missing.ts";'
    assert run_check_with_files("worker_runtime", files).problems


def test_34_4_3_project_references_check_projects_with_external_compiler_settings(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = _workspace({"consumer": {"dependencies": {"provider": "workspace:*"}}, "provider": {}})
    for name in ("consumer", "provider"):
        files[f"packages/{name}/tsconfig.json"] = '{"extends":"external/node.json"}'
    assert run_check_with_files("project_references", files).problems
    files["packages/consumer/tsconfig.json"] = '{"extends":"external/node.json","references":[{"path":"../provider"}]}'
    assert not run_check_with_files("project_references", files).problems


def test_34_6_4_workers_follow_inherited_aliases_and_export_arrays(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = _workspace({"shared": {"exports": {"./api": ["./src/api.ts"]}}})
    files.update({
        "tsconfig.base.json": '{"compilerOptions":{"paths":{"@/*":["apps/worker/src/*"]}}}',
        "apps/worker/tsconfig.json": '{"extends":"../../tsconfig.base.json"}',
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "@/entry";',
        "apps/worker/src/entry.ts": 'import "shared/api";',
        "packages/shared/src/api.ts": 'import "node:fs";',
    })
    assert run_check_with_files("worker_runtime", files).problems
    files["packages/shared/src/api.ts"] = "export const ready = true;"
    assert not run_check_with_files("worker_runtime", files).problems


def test_34_6_5_workers_respect_blocked_exports_and_default_condition_order(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = _workspace({"shared": {"exports": {"./api": {"default": None, "import": "./src/api.ts"}}}})
    files.update({
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "shared/api";',
        "packages/shared/src/api.ts": "export const ready = true;",
    })
    assert run_check_with_files("worker_runtime", files).problems


@pytest.mark.parametrize(
    "overlay",
    [
        "[architecture]\nunknown=true",
        "[architecture]\napplications=1",
        "[[architecture.applications]]\nname=1\nkeeper='domain'\npackages=['domain']",
        "[[architecture.applications]]\nname='app'\nkeeper='domain'\npackages=[]",
        "[[architecture.applications]]\nname='app'\nkeeper='domain'\npackages=['domain']\nunknown=true",
        "[architecture.dependencies]\ndomain=1",
    ],
)
def test_34_7_1_rejects_invalid_architecture_declarations(
    run_check_with_files: RunCheckWithFiles,
    overlay: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        run_check_with_files("contract_keepers", _workspace({"domain": {}}), overlay)


def test_34_6_6_workers_resolve_child_paths_relative_to_their_declaring_config(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    files = {
        "tsconfig.base.json": '{"compilerOptions": {"strict":true}}',
        "apps/worker/tsconfig.json": json.dumps({
            "extends": ["../../tsconfig.base"],
            "compilerOptions": {"paths": {"local": ["./src/entry.ts"]}},
        }),
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "local";',
        "apps/worker/src/entry.ts": 'import "node:fs";',
    }
    assert run_check_with_files("worker_runtime", files).problems
    files["apps/worker/src/entry.ts"] = "export const ready = true;"
    assert not run_check_with_files("worker_runtime", files).problems


@pytest.mark.parametrize("later_base", [None, "alternate"])
@pytest.mark.parametrize("paths_owner", ["base", "worker"])
def test_34_6_7_workers_preserve_or_override_base_url_across_multiple_parents(
    run_check_with_files: RunCheckWithFiles, later_base: str | None, paths_owner: str
) -> None:
    entry = f"{later_base}/src/entry.ts" if later_base is not None else "src/entry.ts"
    aliases = {"paths": {"shared": ["src/entry.ts"]}}
    files = {
        "tsconfig.base.json": json.dumps({
            "compilerOptions": {"baseUrl": ".", **(aliases if paths_owner == "base" else {})}
        }),
        "tsconfig.strict.json": json.dumps({
            "compilerOptions": {"strict": True, **({"baseUrl": later_base} if later_base is not None else {})}
        }),
        "apps/worker/tsconfig.json": json.dumps({
            "extends": ["../../tsconfig.base.json", "../../tsconfig.strict.json"],
            "compilerOptions": aliases if paths_owner == "worker" else {},
        }),
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "shared";',
        "apps/worker/src/entry.ts": "export const ready = true;",
        entry: 'import "node:fs";',
    }
    assert run_check_with_files("worker_runtime", files).problems
    files[entry] = "export const ready = true;"
    assert not run_check_with_files("worker_runtime", files).problems


@pytest.mark.parametrize("later_paths", [{}, {"other": ["src/entry.ts"]}])
def test_34_6_8_workers_replace_parent_path_maps_instead_of_merging_aliases(
    run_check_with_files: RunCheckWithFiles, later_paths: dict[str, list[str]]
) -> None:
    files = _workspace({"shared": {"exports": {".": "./src/index.ts"}}})
    files.update({
        "tsconfig.base.json": '{"compilerOptions":{"baseUrl":".","paths":{"shared":["src/entry.ts"]}}}',
        "tsconfig.strict.json": json.dumps({"compilerOptions": {"paths": later_paths}}),
        "apps/worker/tsconfig.json": '{"extends":["../../tsconfig.base.json","../../tsconfig.strict.json"]}',
        "apps/worker/wrangler.jsonc": '{"main":"src/index.ts"}',
        "apps/worker/src/index.ts": 'import "shared";',
        "packages/shared/src/index.ts": "export const ready = true;",
        "src/entry.ts": 'import "node:fs";',
    })
    assert not run_check_with_files("worker_runtime", files).problems
