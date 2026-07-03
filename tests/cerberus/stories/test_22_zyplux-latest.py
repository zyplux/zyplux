from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from cerberus import config, context, registries
from cerberus.checks import zyplux_latest_check
from cerberus.model import CheckResult, Status

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

NPM_UTIL_LOCK = '{"packages": {"@zyplux/util": ["@zyplux/util@0.2.0", {}, "sha512-x"]}}'
NPM_WORKSPACE_LOCK = (
    '{"workspaces": {"packages/util-ts":'
    ' {"name": "@zyplux/util", "dependencies": {"@zyplux/tsconfig": "workspace:*"}}}}'
)
UV_CERBERUS_LOCK = """
version = 1

[[package]]
name = "zyplux-cerberus"
version = "0.6.0"
source = { registry = "https://pypi.org/simple" }
"""
UV_WORKSPACE_LOCK = """
version = 1

[[package]]
name = "zyplux"
version = "0"
source = { virtual = "." }

[[package]]
name = "zyplux-cerberus"
version = "0.6.0"
source = { editable = "apps/cerberus" }
"""
CI_IMAGE_WORKFLOW = """
jobs:
  ci:
    container: ghcr.io/zyplux/ci:0.1.0
"""


@dataclass
class FakeRegistry:
    payloads: dict[tuple[str, str], object] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)

    def serve_npm(self, package: str, latest: str) -> None:
        encoded = package.replace("/", "%2F")
        self.payloads["registry.npmjs.org", f"/{encoded}"] = {"dist-tags": {"latest": latest}}

    def serve_pypi(self, distribution: str, latest: str) -> None:
        self.payloads["pypi.org", f"/pypi/{distribution}/json"] = {"info": {"version": latest}}

    def serve_ghcr(self, image: str, tags: list[str]) -> None:
        self.payloads["ghcr.io", f"/token?service=ghcr.io&scope=repository:{image}:pull"] = {"token": "anonymous"}
        self.payloads["ghcr.io", f"/v2/{image}/tags/list"] = {"tags": tags}

    def fetch_json(self, host: str, path: str, headers: dict[str, str] | None = None) -> object:
        del headers
        self.requests.append((host, path))
        if (host, path) not in self.payloads:
            failure = f"https://{host}{path}: connection refused"
            raise registries.RegistryLookupError(failure)
        return self.payloads[host, path]


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> FakeRegistry:
    fake = FakeRegistry()
    monkeypatch.setattr(registries, "_fetch_json", fake.fetch_json)
    return fake


def run_check_on(tmp_path: Path, files: dict[str, str]) -> CheckResult:
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    ctx = context.local_context(config.load(), tmp_path)
    return zyplux_latest_check.run(ctx.repos()[0], ctx)


def test_22_1_1_passes_a_repo_that_uses_no_zyplux_published_artifacts(tmp_path: Path, registry: FakeRegistry) -> None:
    files = {
        "bun.lock": '{"packages": {"typescript": ["typescript@5.9.2", {}, "sha512-x"]}}',
        "justfile": "default:\n    @just --list\n",
        ".github/workflows/ci.yml": "jobs:\n  ci:\n    container: ghcr.io/other-org/ci:1.0.0\n",
    }
    result = run_check_on(tmp_path, files)
    assert (result.status, result.problems, registry.requests) == (Status.PASS, [], [])


def test_22_1_2_ignores_workspace_local_zyplux_packages(tmp_path: Path, registry: FakeRegistry) -> None:
    result = run_check_on(tmp_path, {"bun.lock": NPM_WORKSPACE_LOCK, "uv.lock": UV_WORKSPACE_LOCK})
    assert (result.status, result.problems, registry.requests) == (Status.PASS, [], [])


def test_22_1_3_queries_each_artifact_once_per_run(tmp_path: Path, registry: FakeRegistry) -> None:
    registry.serve_ghcr("zyplux/ci", ["0.1.0", "latest"])
    files = {
        ".github/workflows/ci.yml": CI_IMAGE_WORKFLOW,
        ".github/workflows/nightly.yml": CI_IMAGE_WORKFLOW,
        "justfile": "smoke:\n    docker run ghcr.io/zyplux/ci:0.1.0\n",
    }
    result = run_check_on(tmp_path, files)
    assert (result.status, result.problems) == (Status.PASS, [])
    assert registry.requests == [
        ("ghcr.io", "/token?service=ghcr.io&scope=repository:zyplux/ci:pull"),
        ("ghcr.io", "/v2/zyplux/ci/tags/list"),
    ]


def test_22_2_1_passes_when_the_locked_npm_version_is_the_latest(tmp_path: Path, registry: FakeRegistry) -> None:
    registry.serve_npm("@zyplux/util", "0.2.0")
    result = run_check_on(tmp_path, {"bun.lock": NPM_UTIL_LOCK})
    assert (result.status, result.problems) == (Status.PASS, [])


def test_22_2_2_fails_naming_the_package_versions_and_location_when_the_lock_lags(
    tmp_path: Path, registry: FakeRegistry
) -> None:
    registry.serve_npm("@zyplux/util", "0.3.1")
    result = run_check_on(tmp_path, {"bun.lock": NPM_UTIL_LOCK})
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["`@zyplux/util` is 0.2.0 in bun.lock, latest is 0.3.1; run `just upgrade`"],
    )


def test_22_3_1_fails_when_uv_lock_resolves_an_outdated_zyplux_distribution(
    tmp_path: Path, registry: FakeRegistry
) -> None:
    registry.serve_pypi("zyplux-cerberus", "0.7.0")
    result = run_check_on(tmp_path, {"uv.lock": UV_CERBERUS_LOCK})
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["`zyplux-cerberus` is 0.6.0 in uv.lock, latest is 0.7.0; run `just upgrade`"],
    )


def test_22_3_2_fails_a_version_pinned_uvx_run_but_passes_an_unpinned_one(
    tmp_path: Path, registry: FakeRegistry
) -> None:
    registry.serve_pypi("zyplux-cerberus", "0.7.0")
    justfile = "lint:\n    uvx --from zyplux-cerberus==0.6.0 cerberus\n"
    workflow = "jobs:\n  ci:\n    steps:\n      - run: uvx --from zyplux-cerberus cerberus\n"
    result = run_check_on(tmp_path, {"justfile": justfile, ".github/workflows/ci.yml": workflow})
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["`zyplux-cerberus` is 0.6.0 in justfile, latest is 0.7.0; run `just upgrade`"],
    )


def test_22_4_1_fails_when_a_workflow_pins_an_outdated_ghcr_image_tag(tmp_path: Path, registry: FakeRegistry) -> None:
    registry.serve_ghcr("zyplux/ci", ["0.1.0", "0.1.1", "latest"])
    result = run_check_on(tmp_path, {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW})
    assert (result.status, [f.message for f in result.problems]) == (
        Status.FAIL,
        ["`ghcr.io/zyplux/ci` is 0.1.0 in .github/workflows/ci.yml, latest is 0.1.1; run `just upgrade`"],
    )


def test_22_4_2_passes_the_floating_latest_tag(tmp_path: Path, registry: FakeRegistry) -> None:
    workflow = "jobs:\n  ci:\n    container: ghcr.io/zyplux/ci:latest\n"
    result = run_check_on(tmp_path, {".github/workflows/ci.yml": workflow})
    assert (result.status, result.problems, registry.requests) == (Status.PASS, [], [])


def break_token_endpoint(_registry: FakeRegistry) -> str:
    return "https://ghcr.io/token?service=ghcr.io&scope=repository:zyplux/ci:pull: connection refused"


def break_token_payload(registry: FakeRegistry) -> str:
    registry.payloads["ghcr.io", "/token?service=ghcr.io&scope=repository:zyplux/ci:pull"] = {"detail": "denied"}
    return "zyplux/ci: response carries no `token`"


def break_tag_list_shape(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", [])
    registry.payloads["ghcr.io", "/v2/zyplux/ci/tags/list"] = {"tags": "0.1.0"}
    return "zyplux/ci: tag list is not a list"


def break_version_tags(registry: FakeRegistry) -> str:
    registry.serve_ghcr("zyplux/ci", ["latest", "sha-abc123"])
    return "zyplux/ci: no version tags published"


@pytest.mark.parametrize(
    "break_registry",
    [break_token_endpoint, break_token_payload, break_tag_list_shape, break_version_tags],
    ids=lambda scenario: scenario.__name__,
)
def test_22_5_1_errors_instead_of_passing_when_a_registry_lookup_fails(
    tmp_path: Path, registry: FakeRegistry, break_registry: Callable[[FakeRegistry], str]
) -> None:
    failure = break_registry(registry)
    files = {".github/workflows/ci.yml": CI_IMAGE_WORKFLOW, ".github/workflows/nightly.yml": CI_IMAGE_WORKFLOW}
    result = run_check_on(tmp_path, files)
    assert result.status is Status.ERROR
    assert [f.message for f in result.problems] == [f"could not determine the latest `ghcr.io/zyplux/ci`: {failure}"]
