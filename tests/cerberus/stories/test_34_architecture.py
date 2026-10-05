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
    [(False, True), (True, False), (["./src/register.ts"], False), (["./src/other.ts"], True), (None, True)],
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
        "export const messages = async function* () { yield 1; };",
        "export const messages = function* () { yield 1; };",
        "export async function* messages() { yield 1; }",
        "const messages = async function* () { yield 1; }; export const stream = messages();",
    ],
)
def test_34_5_2_pure_libraries_may_declare_no_side_effects(
    run_check_with_files: RunCheckWithFiles, source: str
) -> None:
    files = _workspace({"library": {"exports": {".": "./src/index.ts"}, "sideEffects": False}})
    files["packages/library/src/index.ts"] = source
    assert not run_check_with_files("package_side_effects", files).problems


@pytest.mark.parametrize(
    ("metadata", "has_failure"),
    [
        (["./src/nested/register.ts"], False),
        (["src/**/*.ts"], False),
        (["./dist/nested/register.js"], True),
        ([], True),
    ],
)
def test_34_5_3_matches_side_effects_against_workspace_modules_without_assuming_a_build_directory(
    run_check_with_files: RunCheckWithFiles, metadata: object, *, has_failure: bool
) -> None:
    files = _workspace({
        "library": {
            "exports": {".": "./src/index.ts"},
            "sideEffects": metadata,
            "publishConfig": {"sideEffects": ["./build/nested/register.js"]},
        }
    })
    files["packages/library/src/nested/register.ts"] = "registerMatchers();"
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_failure


@pytest.mark.parametrize("extension", ["js", "mjs", "cjs", "mts", "cts"])
def test_34_5_4_checks_javascript_and_explicit_module_extensions(
    run_check_with_files: RunCheckWithFiles, extension: str
) -> None:
    files = _workspace({"library": {"exports": {".": f"./src/index.{extension}"}, "sideEffects": False}})
    files[f"packages/library/src/index.{extension}"] = "registerMatchers();"
    assert run_check_with_files("package_side_effects", files).problems


@pytest.mark.parametrize(
    ("metadata", "has_failure"),
    [
        (["./src/nested/register.ts"], True),
        (["**/register.*"], False),
        (["./src/nested/register.ts", "./build/nested/register.js"], True),
        (["./src/nested/register.ts", "./build/nested/register.cjs"], True),
        (["./src/nested/register.ts", "./build/nested/register.js", "./build/nested/register.cjs"], False),
    ],
)
@pytest.mark.parametrize("export_pattern", ["nested/register", "nested/*", "*"])
def test_34_5_5_preserves_published_registration_modules_in_every_runtime_condition(
    run_check_with_files: RunCheckWithFiles, metadata: object, export_pattern: str, *, has_failure: bool
) -> None:
    files = _workspace({
        "library": {
            "exports": {f"./{export_pattern}": f"./src/{export_pattern}.ts"},
            "sideEffects": metadata,
            "publishConfig": {
                "exports": {
                    f"./{export_pattern}": {
                        "types": f"./build/{export_pattern}.d.ts",
                        "import": f"./build/{export_pattern}.js",
                        "require": f"./build/{export_pattern}.cjs",
                    }
                }
            },
        }
    })
    files["packages/library/src/nested/register.ts"] = "registerMatchers();"
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_failure


@pytest.mark.parametrize("extension", ["js", "cjs"])
@pytest.mark.parametrize("directive", ["use strict", "use client"])
@pytest.mark.parametrize("has_registration", [False, True])
def test_34_5_6_ignores_string_directives_and_preserves_actual_registration(
    run_check_with_files: RunCheckWithFiles, extension: str, directive: str, *, has_registration: bool
) -> None:
    files = _workspace({"library": {"exports": {".": f"./src/index.{extension}"}, "sideEffects": False}})
    statement = "registerMatchers();" if has_registration else "const ready = true;"
    files[f"packages/library/src/index.{extension}"] = f'"{directive}"; {statement}'
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_registration


@pytest.mark.parametrize(
    ("source", "has_failure"),
    [
        ("module.exports = {value: 1};", False),
        ("exports.value = 1;", False),
        ("module.exports.value = 1;", False),
        ("exports['value'] = 1;", False),
        ("module['exports'] = {value: 1};", False),
        ("module.other = {value: 1};", True),
        ("exports[registerMatchers()] = 1;", True),
        ("module.exports[registerMatchers()].value = 1;", True),
        ("module.exports = () => registerMatchers();", False),
        ("module.exports = {register() { registerMatchers(); }};", False),
        ("module.exports = registerMatchers();", True),
        ("module.exports = {matchers: registerMatchers()};", True),
        ("exports.value = globalThis.counter++;", True),
        ("const register = () => { registerMatchers(); }; module.exports = register();", True),
    ],
)
def test_34_5_7_checks_commonjs_export_initializers(
    run_check_with_files: RunCheckWithFiles, source: str, *, has_failure: bool
) -> None:
    files = _workspace({"library": {"exports": {".": "./src/index.cjs"}, "sideEffects": False}})
    files["packages/library/src/index.cjs"] = source
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_failure


@pytest.mark.parametrize("has_registration", [False, True])
def test_34_5_8_checks_jsx_registration_and_defers_component_bodies(
    run_check_with_files: RunCheckWithFiles, *, has_registration: bool
) -> None:
    files = _workspace({"library": {"exports": {".": "./src/index.jsx"}, "sideEffects": False}})
    source = "export const Component = () => <p>Ready</p>;"
    files["packages/library/src/index.jsx"] = source + ("registerMatchers();" if has_registration else "")
    assert bool(run_check_with_files("package_side_effects", files).problems) is has_registration


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
