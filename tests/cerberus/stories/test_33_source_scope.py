from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cerberus import load_source_scope

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("path", "is_production"),
    [
        ("apps/widget/src/widget.tsx", True),
        ("apps/widget/vite.config.ts", True),
        ("packages/store/src/schema.sql", True),
        ("infra/deploy.py", True),
        ("infra/hosts/server/configuration.nix", True),
        ("infra-old/deploy.py", False),
        ("dev/server.ts", False),
        ("doubles/server.ts", False),
        ("tools/lint/src/cli.py", False),
        ("tests/widget/story.ts", False),
        ("apps/widget/tests/story.ts", False),
        ("apps/widget/src/widget.test.tsx", False),
        ("packages/store/src/store.spec.ts", False),
        ("packages/store/__tests__/fixture.ts", False),
        ("infra/tests/fixture.py", False),
        ("infra/test_deploy.py", False),
        ("infra/deploy_test.py", False),
        ("infra/conftest.py", False),
    ],
)
def test_33_1_1_classifies_application_and_infrastructure_files_with_bundled_defaults(
    tmp_path: Path, path: str, *, is_production: bool
) -> None:
    scope = load_source_scope(tmp_path)

    assert scope.is_production_file(path) is is_production


def test_33_1_2_replaces_production_roots_without_replacing_test_defaults(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text('[source]\nproduction_roots = ["services/internal/*"]\n')

    scope = load_source_scope(tmp_path)

    assert scope.find_production_root("services/internal/worker/src/main.py") == "services/internal/worker"
    assert scope.is_production_file("services/internal/worker/tests/fixture.py") is False
    assert scope.is_production_file("infra/deploy.py") is False
    assert scope.is_production_file("apps/widget/src/widget.tsx") is False


def test_33_1_3_overrides_test_file_patterns_without_replacing_production_defaults(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text('[source]\ntest_files = ["**/checks/**"]\n')

    scope = load_source_scope(tmp_path)

    assert scope.is_production_file("infra/deploy.py") is True
    assert scope.is_production_file("infra/checks/deploy.py") is False
    assert scope.is_test_file("infra/checks/deploy.py") is True


@pytest.mark.parametrize("section", ["knip", "pyrefly"])
def test_33_1_4_explains_how_to_replace_tool_specific_production_settings(tmp_path: Path, section: str) -> None:
    (tmp_path / "cerberus.toml").write_text(f'[{section}]\nprod_workspaces = ["tools/*"]\n')

    with pytest.raises(ValueError, match=rf"Move \[{section}\]\.prod_workspaces to \[source\]\.production_roots"):
        load_source_scope(tmp_path)
