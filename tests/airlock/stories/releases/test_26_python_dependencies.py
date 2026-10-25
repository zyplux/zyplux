from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from archive_fixture import write_tar, write_wheel
from cli_fixture import Response
from release_fixture import prepare_publication

if TYPE_CHECKING:
    from cli_fixture import Command, Request
    from release_fixture import ReleaseFixture

DEPENDENCY_URL = "https://pypi.org/pypi/zyplux-util/1.0.0/json"


def add_python_target(release: ReleaseFixture, name: str, label: str, requirements: tuple[str, ...] = ()) -> None:
    directory = f"packages/{name}"
    release.write(
        f"{directory}/pyproject.toml",
        f'[project]\nname = "{label}"\nversion = "1.0.0"\ndependencies = {json.dumps(requirements)}\n',
    )
    release.write_json(f"{directory}/package.json", {"name": label, "private": True, "version": "1.0.0"})
    release.write(f"{directory}/CHANGELOG.md", f"## 1.0.0\n\n- Publish {label}.\n")
    release.write(
        "airlock-targets.toml",
        release.read("airlock-targets.toml") + f'\n[{name}]\nkind = "pypi"\nlabel = "{label}"\n'
        f'version = {{ file = "{directory}/pyproject.toml", regex = \'^version = "([^"]+)"\' }}\n',
    )


@pytest.fixture
def release(release: ReleaseFixture) -> ReleaseFixture:
    release.write(
        "apps/cerberus/pyproject.toml",
        '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\ndependencies = ["zyplux_util>=1.0.0"]\n',
    )
    add_python_target(release, "runtime", "zyplux-util")
    prepare_publication(release)
    return release


def test_26_1_1_waits_for_complete_dependency_artifacts_before_uploading_the_inspected_build(
    release: ReleaseFixture,
) -> None:
    attempts: list[Request] = []
    visibility_attempts = 2

    def respond(request: Request) -> Response:
        attempts.append(request)
        kinds = ["bdist_wheel"] if len(attempts) == 1 else ["bdist_wheel", "sdist"]
        return Response({"urls": [{"packagetype": kind} for kind in kinds]})

    def publish(_call: Command) -> str:
        assert len(attempts) == visibility_attempts
        return ""

    release.serve(DEPENDENCY_URL, respond)
    release.on("uv publish", publish)
    release.publish("cerberus-v2.3.4")
    assert len(release.matching("uv build")) == 1
    assert len(release.matching("uv publish")) == 1
    release.expect_release("cerberus-v2.3.4")


@pytest.mark.parametrize("status", [404, 200, 502])
def test_26_1_2_blocks_a_missing_dependency_without_blocking_unrelated_releases(
    release: ReleaseFixture, status: int
) -> None:
    release.serve(DEPENDENCY_URL, Response({"urls": [{"packagetype": "bdist_wheel"}]}, status))
    release.publish("cerberus-v2.3.4", error="pypi dependencies did not become available: zyplux-util@1.0.0")
    assert not release.matching("uv publish|gh release create")
    release.stage_npm()
    release.publish("util-v1.2.3")
    release.expect_release("util-v1.2.3")


def test_26_1_3_checks_dependencies_for_optional_and_conditional_installations(release: ReleaseFixture) -> None:
    project = release.read("apps/cerberus/pyproject.toml")
    release.write(
        "apps/cerberus/pyproject.toml",
        project.replace('"zyplux_util>=1.0.0"', "\"zyplux-util[extra]>=1.0.0; python_version < '3.0'\""),
    )
    prepare_publication(release)
    release.publish("cerberus-v2.3.4", error="pypi dependencies did not become available")
    assert not release.matching("uv publish")


def test_26_1_4_propagates_registry_authentication_failures_before_upload(release: ReleaseFixture) -> None:
    release.serve(DEPENDENCY_URL, Response(status=403))
    release.publish("cerberus-v2.3.4", error="failed: 403")
    assert not release.matching("uv publish")


@pytest.mark.parametrize(
    "requirement", ["zyplux-util<1.0", "external>=1.0", "zyplux-util @ https://example.com/runtime.whl"]
)
def test_26_2_1_ignores_dependencies_that_do_not_use_a_configured_workspace_version(
    release: ReleaseFixture, requirement: str
) -> None:
    release.write(
        "apps/cerberus/pyproject.toml",
        f'[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\ndependencies = {json.dumps([requirement])}\n',
    )
    prepare_publication(release)
    release.on("uv publish")
    release.publish("cerberus-v2.3.4")
    assert not any(request.url == DEPENDENCY_URL for request in release.requests)


@pytest.mark.parametrize("problem", ["missing", "identity", "version", "requirement", "multiple"])
def test_26_2_2_rejects_invalid_wheel_metadata_before_upload(release: ReleaseFixture, problem: str) -> None:
    def build(call: Command) -> str:
        directory = Path(call.argv[call.argv.index("--out-dir") + 1])
        metadata = "Metadata-Version: 2.4\nName: zyplux-cerberus\nVersion: 2.3.4\n"
        if problem == "identity":
            metadata = metadata.replace("zyplux-cerberus", "wrong-package")
        elif problem == "version":
            metadata = metadata.replace("2.3.4", "2.3.5")
        elif problem == "requirement":
            metadata += "Requires-Dist: [\n"
        write_wheel(
            directory / "package.whl", {} if problem == "missing" else {"pkg.dist-info/METADATA": metadata.encode()}
        )
        write_tar(directory / "package.tar.gz", {"package/source.py": b"source"})
        if problem == "multiple":
            write_wheel(directory / "other.whl", {"pkg.dist-info/METADATA": metadata.encode()})
        return ""

    release.on("uv build", build)
    prepare_publication(release)
    execution = release.publish("cerberus-v2.3.4", error="wheel")
    assert "Traceback" not in execution.stderr
    assert not release.matching("uv publish|gh release create")


def test_26_2_3_rejects_self_dependencies_before_upload(release: ReleaseFixture) -> None:
    release.write(
        "apps/cerberus/pyproject.toml",
        release.read("apps/cerberus/pyproject.toml").replace("zyplux_util>=1.0.0", "zyplux-cerberus>=2.0.0"),
    )
    prepare_publication(release)
    release.publish("cerberus-v2.3.4", error="cyclic production workspace dependency")
    assert not release.matching("uv publish")


@pytest.mark.parametrize("has_transitive", [False, True])
def test_26_3_1_rejects_cycles_before_waiting_and_keeps_unrelated_jobs_independent(
    release: ReleaseFixture, *, has_transitive: bool
) -> None:
    requirement = "zyplux-cerberus>=2.3.4"
    if has_transitive:
        add_python_target(release, "extra", "zyplux-extra", (requirement,))
        requirement = "zyplux-extra>=1.0.0"
    release.write(
        "packages/runtime/pyproject.toml",
        release.read("packages/runtime/pyproject.toml").replace(
            "dependencies = []", f"dependencies = {json.dumps([requirement])}"
        ),
    )
    prepare_publication(release)
    execution = release.publish("cerberus-v2.3.4", error="cyclic production workspace dependency")
    assert "zyplux-util" in execution.stderr
    assert "zyplux-cerberus" in execution.stderr
    assert len([request for request in release.requests if request.url == DEPENDENCY_URL]) == 1
    assert len(release.matching("uv build")) == 1
    assert not release.matching("uv publish|gh release create")
    release.stage_npm()
    release.publish("util-v1.2.3")
    release.expect_release("util-v1.2.3")


@pytest.mark.parametrize("has_transient", [False, True])
def test_26_3_2_allows_an_existing_publication_to_break_a_dependency_cycle(
    release: ReleaseFixture, *, has_transient: bool
) -> None:
    release.write(
        "packages/runtime/pyproject.toml",
        release.read("packages/runtime/pyproject.toml").replace(
            "dependencies = []", 'dependencies = ["zyplux-cerberus>=2.3.4"]'
        ),
    )
    prepare_publication(release)
    complete = Response({"urls": [{"packagetype": kind} for kind in ("bdist_wheel", "sdist")]})
    replies = iter([Response(status=502), complete] if has_transient else [complete])
    release.serve(DEPENDENCY_URL, lambda _request: next(replies, complete))
    release.on("uv publish")
    release.publish("cerberus-v2.3.4")
    assert len(release.matching("uv build")) == 1
    release.expect_release("cerberus-v2.3.4")


def test_26_3_3_includes_optional_dependencies_in_cycle_detection(release: ReleaseFixture) -> None:
    release.write(
        "packages/runtime/pyproject.toml",
        release.read("packages/runtime/pyproject.toml")
        + '\n[project.optional-dependencies]\nconsumer = ["zyplux-cerberus>=2.3.4"]\n',
    )
    prepare_publication(release)
    release.publish("cerberus-v2.3.4", error="cyclic production workspace dependency")
    assert not release.matching("uv publish")


@pytest.mark.parametrize("has_project", [True, False])
def test_26_3_4_requires_dynamic_workspace_dependencies_to_publish_first(
    release: ReleaseFixture, *, has_project: bool
) -> None:
    release.write(
        "packages/runtime/pyproject.toml",
        ("[project]\n" if has_project else "")
        + 'name = "zyplux-util"\nversion = "1.0.0"\ndynamic = ["dependencies"]\n',
    )
    release.publish("cerberus-v2.3.4", error="publish dynamic workspace dependencies before their consumers")
    assert not release.matching("uv publish")
