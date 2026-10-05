from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from cerberus.model import CheckResult
    from seam_fixtures import MakeFinding

type RunCheckWithFiles = Callable[[str, Mapping[str, str | None]], CheckResult]
type RunVitestCoverage = Callable[[Mapping[str, str | None]], CheckResult]

CHECK_ID = "vitest_coverage"

_COMPLIANT_CONFIG = (
    "export default defineConfig({\n"
    "  test: {\n"
    "    coverage: {\n"
    "      enabled: true,\n"
    "      thresholds: {\n"
    "        branches: 90,\n"
    "        functions: 90,\n"
    "        lines: 90,\n"
    "        statements: 90,\n"
    "      },\n"
    "    },\n"
    "  },\n"
    "});\n"
)

_SKIP_MESSAGE = "no root Vitest coverage configuration or TypeScript tests"
_NO_COVERAGE_MESSAGE = (
    "vitest.config.ts: exported test.coverage.thresholds must resolve to a literal object enforcing at least 90%"
)
_NO_COLLECTION_MESSAGE = (
    "vitest.config.ts: enable coverage with test.coverage.enabled: true or the root test script's --coverage flag"
)
_TEST_SETUP = (
    "const floor = 90; const thresholds = {branches: floor, functions: floor, lines: floor, statements: floor};"
    "const coverage = {enabled: true, thresholds}; const test = {coverage};"
)


@pytest.fixture
def run_vitest_coverage(run_check_with_files: RunCheckWithFiles) -> RunVitestCoverage:
    return partial(run_check_with_files, CHECK_ID)


def test_19_1_1_ignores_a_nested_vitest_config_that_is_not_at_the_repo_root(
    run_vitest_coverage: RunVitestCoverage, skip: MakeFinding
) -> None:
    files = {"packages/a/vitest.config.ts": "export default defineProject({ test: {} });\n"}

    result = run_vitest_coverage(files)

    assert result.findings == [skip(_SKIP_MESSAGE)]


def test_19_2_1_errors_when_the_root_vitest_config_cannot_be_read(
    run_vitest_coverage: RunVitestCoverage, error: MakeFinding
) -> None:
    result = run_vitest_coverage({"vitest.config.ts": None})

    assert result.findings == [error("could not read vitest.config.ts")]


def test_19_2_2_fails_when_the_coverage_block_is_unterminated(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    files = {"vitest.config.ts": "export default defineConfig({ test: { coverage: { thresholds: {\n"}

    result = run_vitest_coverage(files)

    assert result.findings == [fail("vitest.config.ts: invalid TypeScript coverage configuration")]


def test_19_3_1_fails_when_the_config_has_no_coverage_block(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    files = {"vitest.config.ts": "export default defineConfig({ test: {} });\n"}

    result = run_vitest_coverage(files)

    assert result.findings == [fail(_NO_COVERAGE_MESSAGE)]


def test_19_3_2_fails_when_the_coverage_block_has_no_thresholds(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    files = {"vitest.config.ts": "export default defineConfig({ test: { coverage: { provider: 'istanbul' } } });\n"}

    result = run_vitest_coverage(files)

    assert result.findings == [
        fail(
            _NO_COVERAGE_MESSAGE,
        )
    ]


def test_19_4_1_fails_and_names_the_metric_when_a_threshold_is_below_the_required_floor(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    files = {"vitest.config.ts": _COMPLIANT_CONFIG.replace("branches: 90", "branches: 80")}

    result = run_vitest_coverage(files)

    assert result.findings == [fail("vitest.config.ts coverage.thresholds.branches is 80.0, below the required 90")]


def test_19_4_2_fails_when_a_threshold_metric_is_missing(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    files = {"vitest.config.ts": _COMPLIANT_CONFIG.replace("branches: 90,\n", "")}

    result = run_vitest_coverage(files)

    assert result.findings == [
        fail("vitest.config.ts coverage.thresholds has no literal `branches`; must be set to at least 90")
    ]


def test_19_4_3_rejects_functions_in_numeric_threshold_fields(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    source = _COMPLIANT_CONFIG.replace("branches: 90", "branches: () => 90")
    assert run_vitest_coverage({"vitest.config.ts": source}).findings == [
        fail("vitest.config.ts coverage.thresholds has no literal `branches`; must be set to at least 90")
    ]


def test_19_5_1_passes_when_every_threshold_metric_meets_the_required_floor(
    run_vitest_coverage: RunVitestCoverage, ok: MakeFinding
) -> None:
    result = run_vitest_coverage({"vitest.config.ts": _COMPLIANT_CONFIG})

    assert result.findings == [ok("Vitest coverage gate enforces >= 90%")]


@pytest.mark.parametrize(
    "config",
    [
        "export default {test};",
        "const config = defineConfig({test}); export default config;",
        "const config = {test}; const selected = config; export default selected;",
        "export default ({test} satisfies ViteUserConfig);",
        "export default ({test} as const);",
        "export default defineConfig(() => ({test}));",
        "export default defineConfig(() => { return {test}; });",
        "export default defineConfig(function () { return {test}; });",
        "import {defineConfig as createConfig} from 'vitest/config'; export default createConfig({test});",
    ],
)
def test_19_5_2_resolves_local_constants_typed_objects_and_vitest_config_helpers(
    run_vitest_coverage: RunVitestCoverage, ok: MakeFinding, config: str
) -> None:
    source = _TEST_SETUP + config
    assert run_vitest_coverage({"vitest.config.ts": source}).findings == [ok("Vitest coverage gate enforces >= 90%")]


@pytest.mark.parametrize(
    "config",
    [
        "const config = other; const other = config; export default config;",
        "let config = {test}; export default config;",
        "export default transform({test});",
        "export default defineConfig(({test}) => ({test}));",
        "const defineConfig = transform; export default defineConfig({test});",
        "export default defineConfig(() => { if (condition) return {test}; return {}; });",
        "export default defineConfig(() => {});",
    ],
)
def test_19_5_3_rejects_unresolved_cycles_mutable_configs_and_unknown_transformations(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding, config: str
) -> None:
    source = _TEST_SETUP + config
    assert run_vitest_coverage({"vitest.config.ts": source}).findings == [fail(_NO_COVERAGE_MESSAGE)]


def test_19_5_4_ignores_coverage_in_unrelated_nested_objects(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    source = _COMPLIANT_CONFIG.replace("test: {", "unrelated: { test: {").replace("});", "}});")
    assert run_vitest_coverage({"vitest.config.ts": source}).findings == [fail(_NO_COVERAGE_MESSAGE)]


@pytest.mark.parametrize(
    ("script", "has_coverage"),
    [
        ("vitest run --coverage", True),
        ("vitest run --coverage.enabled", True),
        ("pnpm exec vitest run --coverage.enabled=true", True),
        ("npx vitest run --coverage=true", True),
        ("pnpm vitest run --coverage", True),
        ("bunx vitest run --coverage", True),
        ("NODE_ENV=test vitest run --coverage", True),
        ('NODE_ENV=test LABEL="two words" pnpm exec vitest run --coverage.enabled=true', True),
        ("vitest run", False),
        ("vitest run --coverage.enabled=false", False),
        ("vitest run --coverage=false", False),
        ("vitest run --coverage false", False),
        ("vitest run --coverage --coverage.enabled=false", False),
        ("echo 'vitest run --coverage'", False),
        ("vitest run && echo --coverage", False),
        ("vitest run --coverage && echo finished", True),
    ],
)
def test_19_6_1_requires_coverage_collection_in_config_or_the_root_test_command(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding, ok: MakeFinding, script: str, *, has_coverage: bool
) -> None:
    files = {
        "vitest.config.ts": _COMPLIANT_CONFIG.replace("enabled: true", "enabled: false"),
        "package.json": json.dumps({"scripts": {"test": script}}),
    }
    expected = ok("Vitest coverage gate enforces >= 90%") if has_coverage else fail(_NO_COLLECTION_MESSAGE)
    assert run_vitest_coverage(files).findings == [expected]


def test_19_6_2_requires_explicit_collection_when_coverage_enabled_is_absent(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding
) -> None:
    source = _COMPLIANT_CONFIG.replace("      enabled: true,\n", "")
    assert run_vitest_coverage({"vitest.config.ts": source}).findings == [fail(_NO_COLLECTION_MESSAGE)]


@pytest.mark.parametrize("flag", ["--coverage.enabled=false", "--coverage=false", "--coverage false"])
@pytest.mark.parametrize("prefix", ["", "NODE_ENV=test ", 'NODE_ENV=test LABEL="two words" '])
def test_19_6_3_cli_coverage_flags_override_enabled_configuration(
    run_vitest_coverage: RunVitestCoverage, fail: MakeFinding, flag: str, prefix: str
) -> None:
    files = {
        "vitest.config.ts": _COMPLIANT_CONFIG,
        "package.json": json.dumps({"scripts": {"test": f"{prefix}vitest run {flag}"}}),
    }
    assert run_vitest_coverage(files).findings == [fail(_NO_COLLECTION_MESSAGE)]
