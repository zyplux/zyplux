from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from coverage import Coverage

if TYPE_CHECKING:
    from repository_fixture import ReportRepo
    from seam_fixtures import ConfigureCoverage, RunCheckWithFiles

SOURCE = '[source]\ndemo_roots = ["infra/demo", "tests/demo"]\n'
COVERAGE_FLOOR = 90
PYTEST_CONFIG = """
[tool.pytest.ini_options]
addopts = "-p cerberus --cov --cov-report=json"
testpaths = ["tests"]
[tool.coverage.run]
plugins = ["cerberus.coverage_plugin"]
patch = ["subprocess"]
[tool.coverage.report]
fail_under = 90
"""


def run_pytest(report_repo: ReportRepo, *args: str) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith("COVERAGE_")}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "pytest_cov", "-q", *args],
        cwd=report_repo.root,
        env={**env, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        check=False,
        text=True,
        capture_output=True,
    )


def test_40_1_1_derives_coverage_from_all_eligible_kinds(
    report_repo: ReportRepo, configure_coverage: ConfigureCoverage
) -> None:
    report_repo.write("cerberus.toml", SOURCE)
    for path in (
        "apps/api/src/api.py",
        "infra/cloudflare/src/deploy.py",
        "tools/lint/cli.py",
        "infra/demo/src/deploy.py",
        "tests/api/fixture.py",
        "doubles/fixture.py",
    ):
        report_repo.write(path, "message = 'hello'\n")
    coverage = Coverage(config_file=False)
    coverage.set_option("run:plugins", ["cerberus.coverage_plugin"])
    configure_coverage(coverage)
    assert coverage.get_option("run:source") == [
        str(report_repo.root / path) for path in ("apps/api/src", "infra/cloudflare/src", "tools/lint")
    ]
    omitted = coverage.get_option("run:omit")
    assert isinstance(omitted, list)
    assert set(omitted) == {
        str(report_repo.root / path)
        for path in ("infra/demo/src/deploy.py", "tests/api/fixture.py", "doubles/fixture.py")
    }
    assert coverage.get_option("report:include_namespace_packages") is True
    assert coverage.get_option("run:plugins") == []


def test_40_1_2_excludes_explicit_testing_exemptions_and_empty_source_sets(
    report_repo: ReportRepo, configure_coverage: ConfigureCoverage
) -> None:
    report_repo.write("cerberus.toml", '[source]\ntest_exempt_files = ["tools/local.py"]\n')
    report_repo.write("tools/local.py", "print('local helper')\n")
    coverage = Coverage(config_file=False)
    coverage.set_option("run:plugins", ["cerberus.coverage_plugin"])
    configure_coverage(coverage)
    assert coverage.get_option("run:omit") == ["*"]


def test_40_1_3_excludes_examples_nested_inside_workspace_packages(
    report_repo: ReportRepo, configure_coverage: ConfigureCoverage
) -> None:
    report_repo.write("apps/api/src/api.py", "message = 'product'\n")
    report_repo.write("apps/api/examples/demo.py", "message = 'example'\n")
    report_repo.write("packages/client/examples/demo.py", "message = 'example'\n")
    coverage = Coverage(config_file=False)
    configure_coverage(coverage)
    assert coverage.get_option("run:source") == [str(report_repo.root / "apps/api/src")]
    omitted = coverage.get_option("run:omit")
    assert isinstance(omitted, list)
    assert set(omitted) == {
        str(report_repo.root / "apps/api/examples/demo.py"),
        str(report_repo.root / "packages/client/examples/demo.py"),
    }


def test_40_2_1_skips_demo_suites_and_counts_unexecuted_modules_and_subprocesses(report_repo: ReportRepo) -> None:
    report_repo.write("cerberus.toml", SOURCE)
    report_repo.write("pyproject.toml", PYTEST_CONFIG)
    eligible = ["apps/api/src/api/main.py", "infra/cloudflare/src/deploy.py", "tools/lint/cli.py"]
    for path in (*eligible, "tools/lint/child.py", "infra/demo/src/deploy.py", "tests/product/demo_fixture.py"):
        report_repo.write(path, "message = 'hello'\n")
    cold = "apps/api/src/api/cold.py"
    report_repo.write(cold, "def never_called():\n    return 42\n")
    report_repo.write("tests/demo/test_demo.py", 'raise RuntimeError("demo tests must not be collected")\n')
    outside = report_repo.root.parent / "child-workdir"
    outside.mkdir()
    report_repo.write(
        "tests/product/test_product.py",
        f"""
import runpy
import subprocess
import sys
from pathlib import Path

def test_product_with_demo_fixtures():
    root = Path(__file__).parents[2]
    for path in {[*eligible, "infra/demo/src/deploy.py", "tests/product/demo_fixture.py"]!r}:
        runpy.run_path(str(root / path))
    subprocess.run([sys.executable, str(root / "tools/lint/child.py")], cwd={str(outside)!r}, check=True)
""",
    )
    execution = run_pytest(report_repo)
    assert execution.returncode == 1, execution.stdout + execution.stderr
    assert "1 passed" in execution.stdout
    report = json.loads(report_repo.read("coverage.json"))
    assert set(report["files"]) == {*eligible, cold, "tools/lint/child.py"}
    assert report["files"][cold]["summary"]["covered_lines"] == 0
    assert report["files"]["tools/lint/child.py"]["summary"]["covered_lines"] == 1
    assert report["totals"]["percent_covered"] < COVERAGE_FLOOR


def test_40_2_2_excludes_ignored_python_files_below_coverage_source_directories(report_repo: ReportRepo) -> None:
    report_repo.write("pyproject.toml", PYTEST_CONFIG)
    report_repo.write(".gitignore", "build/\n")
    report_repo.write("product.py", "answer = 42\n")
    report_repo.write("build/generated.py", "answer = 'generated'\n")
    report_repo.write("build/cold.py", "def unused():\n    return 0\n")
    report_repo.write(
        "tests/test_product.py",
        "import runpy\nfrom pathlib import Path\n\n"
        "def test_product():\n    root = Path(__file__).parents[1]\n"
        "    runpy.run_path(str(root / 'product.py'))\n"
        "    runpy.run_path(str(root / 'build/generated.py'))\n",
    )
    execution = run_pytest(report_repo)
    assert execution.returncode == 0, execution.stdout + execution.stderr
    report = json.loads(report_repo.read("coverage.json"))
    assert set(report["files"]) == {"product.py"}
    assert report["files"]["product.py"]["summary"]["missing_lines"] == 0


def test_40_2_3_allows_collection_outside_the_configuration_root(report_repo: ReportRepo) -> None:
    config = report_repo.write("pyproject.toml", PYTEST_CONFIG)
    product = report_repo.write("product.py", "answer = 42\n")
    outside = report_repo.root.parent / "external-tests"
    outside.mkdir()
    (outside / "test_external.py").write_text(
        f"import runpy\n\ndef test_external():\n    assert runpy.run_path({str(product)!r})['answer'] == 42\n"
    )
    execution = run_pytest(report_repo, "-c", str(config), str(outside))
    assert execution.returncode == 0, execution.stdout + execution.stderr
    assert "1 passed" in execution.stdout


def test_40_3_1_requires_stories_for_infrastructure_and_tools_but_not_demo_or_harnesses(
    run_check_with_files: RunCheckWithFiles,
) -> None:
    project = '[project]\nname = "fixture"\n[project.scripts]\nfixture = "fixture:main"\n'
    files = {
        "pyproject.toml": '[tool.uv.workspace]\nmembers = ["infra/*", "tools/*", "doubles", "tests/*"]\n',
        **{
            f"{directory}/pyproject.toml": project
            for directory in ("infra/demo", "infra/deploy", "tools/lint", "doubles", "tests/support")
        },
    }
    result = run_check_with_files("story_tests_lockstep_py", files, SOURCE)
    assert {finding.message.split(":", 1)[0] for finding in result.problems} == {"infra/deploy", "tools/lint"}


def test_40_3_2_keeps_demo_and_harness_code_in_strict_typechecking(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files(
        "pyrefly",
        {
            "pyproject.toml": "[project]\n",
            "pyrefly.toml": 'preset = "strict"\nmin-severity = "warn"\nproject-includes = ["apps"]\n'
            "disable-project-excludes-heuristics = true\nuse-ignore-files = false\n",
            "infra/demo/deploy.py": "",
            "tools/lint/cli.py": "",
            "doubles/fixture.py": "",
        },
        SOURCE,
    )
    assert any("doubles, infra/demo, tools" in finding.message for finding in result.problems)
