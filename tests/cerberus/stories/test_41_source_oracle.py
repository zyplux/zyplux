from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from cerberus import SourceKind, load_source_oracle
from cerberus.cli import app
from typer.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    from seam_fixtures import RunCheckWithFiles


def test_41_1_1_accepts_bundled_category_defaults(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files(
        "source_oracle",
        dict.fromkeys(
            (
                "apps/api/src/main.py",
                "packages/util/index.ts",
                "infra/deploy.py",
                "tools/lint/cli.py",
                "demo/server/main.py",
                "apps/api/examples/main.py",
                "tests/api/test_api.py",
                "doubles/server/main.py",
                "docs/issues/capture.py",
                "docs/tests/test_example.py",
                "scripts/merge-coverage.ts",
            ),
            "",
        ),
    )
    assert not result.problems


@pytest.mark.parametrize("kind", list(SourceKind))
def test_41_1_2_overrides_one_category_and_retains_all_other_defaults(tmp_path: Path, kind: SourceKind) -> None:
    defaults = load_source_oracle(tmp_path)
    (tmp_path / "cerberus.toml").write_text(f'[source_oracle.types.{kind}]\nroots = ["custom/*"]\n')
    expected = {**defaults.types, kind: replace(defaults.types[kind], roots=("custom/*",))}
    assert load_source_oracle(tmp_path) == replace(defaults, types=expected)


def test_41_1_3_overrides_every_category(tmp_path: Path, run_check_with_files: RunCheckWithFiles) -> None:
    directories = dict(zip(SourceKind, ("product", "platform", "showcase", "harness", "manual"), strict=True))
    overlay = "".join(
        f'[source_oracle.types.{kind}]\nroots = ["{directory}/*"]\n' for kind, directory in directories.items()
    )
    paths = [f"{directory}/example/main.py" for directory in directories.values()]
    result = run_check_with_files("source_oracle", dict.fromkeys(paths, ""), overlay)
    assert not result.problems
    oracle = load_source_oracle(tmp_path)
    assert [oracle.classify(path).kind for path in paths] == list(SourceKind)


@pytest.mark.parametrize("parent", [SourceKind.DEMO, SourceKind.DOCS])
@pytest.mark.parametrize("child", list(SourceKind))
def test_41_2_1_enforces_shared_nesting_policies(
    run_check_with_files: RunCheckWithFiles, parent: SourceKind, child: SourceKind
) -> None:
    if parent is child:
        return
    result = run_check_with_files(
        "source_oracle",
        {"content/runtime/main.py": ""},
        f'[source_oracle.types.{parent}]\nroots = ["content"]\n'
        f'[source_oracle.types.{child}]\nroots = ["content/runtime"]\n',
    )
    assert any(
        f"{parent} scope content cannot contain {child} scope content/runtime" in finding.message
        for finding in result.problems
    )


def test_41_2_2_rejects_equally_specific_conflicting_categories(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files(
        "source_oracle",
        {"apps/a/main.py": ""},
        '[source_oracle.types.prod]\nroots = ["apps/*"]\n[source_oracle.types.infra]\nroots = ["apps/?"]\n',
    )
    assert any("conflicting categories" in finding.message for finding in result.problems)


@pytest.mark.parametrize("policy", ["needs_tests = false", 'allowed_child_types = ["prod"]'])
def test_41_2_3_rejects_consumer_policy_overrides(tmp_path: Path, policy: str) -> None:
    (tmp_path / "cerberus.toml").write_text(f"[source_oracle.types.infra]\n{policy}\n")
    with pytest.raises(ValueError, match="overrides may change only roots"):
        load_source_oracle(tmp_path)


def test_41_3_1_exposes_the_same_classification_to_non_python_callers(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name in ("docs/diagnostic.py", "apps/api/src/main.ts", "apps/api/src/main.test.ts"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    result = CliRunner().invoke(app, ["source-oracle", str(tmp_path)])
    assert result.exit_code == 0, result.output
    snapshot = json.loads(result.output)
    oracle = load_source_oracle(tmp_path)
    for path, classification in snapshot.items():
        source = oracle.classify(path)
        assert classification == {
            "kind": source.kind,
            "root": source.root,
            "is_test": source.is_test,
            "needs_tests": source.needs_tests,
        }
