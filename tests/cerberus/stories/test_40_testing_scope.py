from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seam_fixtures import RunCheckWithFiles


def test_40_1_1_requires_stories_only_for_packages_that_need_tests(run_check_with_files: RunCheckWithFiles) -> None:
    project = '[project]\nname = "fixture"\n[project.scripts]\nfixture = "fixture:main"\n'
    directories = ("apps/api", "infra/deploy", "tools/lint", "demo/site", "doubles", "tests/support", "docs/samples")
    files = {
        "pyproject.toml": "[tool.uv.workspace]\n"
        'members = ["apps/*", "infra/*", "demo/*", "tools/*", "doubles", "tests/*", "docs/*"]\n',
        **{f"{directory}/pyproject.toml": project for directory in directories},
    }
    result = run_check_with_files("story_tests_lockstep_py", files)
    assert {finding.message.split(":", 1)[0] for finding in result.problems} == {
        "apps/api",
        "infra/deploy",
        "tools/lint",
    }


def test_40_1_2_keeps_every_category_in_strict_typechecking(run_check_with_files: RunCheckWithFiles) -> None:
    result = run_check_with_files(
        "pyrefly",
        {
            "pyproject.toml": "[project]\n",
            "pyrefly.toml": 'preset = "strict"\nmin-severity = "warn"\nproject-includes = ["apps"]\n'
            "disable-project-excludes-heuristics = true\nuse-ignore-files = false\n",
            "demo/site/deploy.py": "",
            "tools/lint/cli.py": "",
            "doubles/fixture.py": "",
            "docs/diagnostics/capture.py": "",
        },
    )
    assert any("demo, docs, doubles, tools/lint" in finding.message for finding in result.problems)
