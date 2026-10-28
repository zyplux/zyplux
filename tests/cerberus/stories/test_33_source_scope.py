from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cerberus import SourceClassification, SourceKind, load_source_oracle

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("path", "is_production"),
    [
        ("apps/widget/src/widget.tsx", True),
        ("apps/widget/vite.config.ts", True),
        ("apps/widget/examples/demo.py", False),
        ("packages/store/examples/demo.py", False),
        ("packages/store/src/schema.sql", True),
        ("infra/deploy.py", False),
        ("infra/hosts/server/configuration.nix", False),
        ("infra-old/deploy.py", False),
        ("dev/server.ts", False),
        ("doubles/server.ts", False),
        ("tools/lint/src/cli.py", True),
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
    scope = load_source_oracle(tmp_path)

    assert scope.is_production_file(path) is is_production


def test_33_1_2_replaces_production_roots_without_replacing_test_defaults(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text('[source_oracle.types.prod]\nroots = ["services/internal/*"]\n')

    scope = load_source_oracle(tmp_path)

    assert scope.find_production_root("services/internal/worker/src/main.py") == "services/internal/worker"
    assert scope.is_production_file("services/internal/worker/tests/fixture.py") is False
    assert scope.is_production_file("infra/deploy.py") is False
    assert scope.is_production_file("apps/widget/src/widget.tsx") is False


def test_33_1_3_overrides_test_file_patterns_without_replacing_production_defaults(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text('[source_oracle]\ntest_files = ["**/checks/**"]\n')

    scope = load_source_oracle(tmp_path)

    assert scope.is_production_file("apps/widget/deploy.py") is True
    assert scope.is_production_file("apps/widget/checks/deploy.py") is False
    assert scope.is_test_file("apps/widget/checks/deploy.py") is True


@pytest.mark.parametrize(
    ("path", "kind", "root", "flags"),
    [
        ("apps/api/src/demo_client.py", SourceKind.PROD, "apps/api", (False, True)),
        ("infra/cloudflare/src/deploy.py", SourceKind.INFRA, "infra", (False, True)),
        ("tools/lint/src/cli.py", SourceKind.PROD, "tools/lint", (False, True)),
        ("infra/demo/src/deploy.py", SourceKind.DEMO, "infra/demo", (False, False)),
        ("tests/demo/test_deploy.py", SourceKind.DEMO, "tests/demo", (True, False)),
        ("tests/api/test_demo_fixture.py", SourceKind.TEST, "tests", (True, False)),
        ("doubles/server/src/server.ts", SourceKind.TEST, "doubles", (True, False)),
        ("apps/api/src/api.test.ts", SourceKind.PROD, "apps/api", (True, False)),
        ("apps/api/tests/fixture.py", SourceKind.PROD, "apps/api", (True, False)),
        ("custom/tool.py", SourceKind.INFRA, ".", (False, True)),
        ("docs/issues/capture.py", SourceKind.DOCS, "docs", (False, False)),
        ("docs/tests/test_example.py", SourceKind.DOCS, "docs", (True, False)),
        ("scripts/merge-coverage.ts", SourceKind.TEST, "scripts/merge-coverage.ts", (True, False)),
    ],
)
def test_33_2_1_separates_categories_from_colocated_tests_and_testing_eligibility(
    tmp_path: Path, path: str, kind: SourceKind, root: str, flags: tuple[bool, bool]
) -> None:
    (tmp_path / "cerberus.toml").write_text('[source_oracle.types.demo]\nroots = ["infra/demo", "tests/demo"]\n')
    classification = load_source_oracle(tmp_path).classify(path)
    assert classification == SourceClassification(kind, root, *flags)


def test_33_2_2_prefers_deeper_and_more_specific_categories(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text(
        '[source_oracle.types.infra]\nroots = ["apps/api"]\n'
        '[source_oracle.types.prod]\nroots = ["apps/*", "apps/api/runtime"]\n'
    )
    scope = load_source_oracle(tmp_path)
    assert scope.classify("apps/api/cli.py").kind is SourceKind.INFRA
    assert scope.classify("apps/api/runtime/service.py").kind is SourceKind.PROD
    assert scope.classify_directory("apps/api/runtime").kind is SourceKind.PROD
    assert scope.classify_directory("apps/api").kind is SourceKind.INFRA


def test_33_2_3_rejects_ambiguous_categories(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text(
        '[source_oracle.types.prod]\nroots = ["apps/*"]\n[source_oracle.types.demo]\nroots = ["apps/?"]\n'
    )
    with pytest.raises(ValueError, match="conflicting categories"):
        load_source_oracle(tmp_path).classify("apps/a/cli.py")


def test_33_2_4_keeps_testing_exceptions_in_the_shared_declaration(tmp_path: Path) -> None:
    (tmp_path / "cerberus.toml").write_text(
        '[source_oracle]\ntest_exempt_files = ["apps/clipy/src/clipy/justpty.py"]\n'
    )
    classification = load_source_oracle(tmp_path).classify("apps/clipy/src/clipy/justpty.py")
    assert classification.kind is SourceKind.PROD
    assert classification.needs_tests is False
    assert classification.is_test is False


@pytest.mark.parametrize("path", ["apps/demo/runtime/service.py", "apps/demo/tests/test_demo.py"])
def test_33_2_5_rejects_other_categories_inside_demos(tmp_path: Path, path: str) -> None:
    (tmp_path / "cerberus.toml").write_text(
        '[source_oracle.types.demo]\nroots = ["apps/demo"]\n'
        '[source_oracle.types.prod]\nroots = ["apps/*", "apps/demo/runtime"]\n'
        '[source_oracle.types.test]\nroots = ["tests", "apps/demo/tests"]\n'
    )
    with pytest.raises(ValueError, match="demo scope apps/demo cannot contain"):
        load_source_oracle(tmp_path).classify(path)
