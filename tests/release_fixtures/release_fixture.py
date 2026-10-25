from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from archive_fixture import stage_packagers
from cli_fixture import REPO_ROOT, CliFixture, Command, Reply, Response

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Iterator

MANIFEST = """scope = "@zyplux"
[util]
kind = "npm"
version = { file = "packages/util/package.json", json = "version" }
[cerberus]
kind = "pypi"
label = "zyplux-cerberus"
version = { file = "apps/cerberus/pyproject.toml", regex = '^version = "([^"]+)"' }
[ci-image]
kind = "ghcr"
label = "ghcr.io/zyplux/ci"
version = { file = "containers/ci/Containerfile", regex = '^LABEL org\\.opencontainers\\.image\\.version="([^"]+)"' }
"""

PACKAGE_MANIFEST = """scope = "@zyplux"
[util]
kind = "npm"
version = { file = "packages/util/package.json", json = "version" }
"""
MISSING_RELEASE = json.dumps({"data": {"repository": {"release": None}}})
PUBLISHED_RELEASE = json.dumps({
    "data": {
        "repository": {
            "release": {
                "id": "release-id",
                "isDraft": False,
                "releaseAssets": {"nodes": [{"name": "release.json"}]},
            }
        }
    }
})


def build_release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict[str, Any]:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


@dataclass(frozen=True)
class Target:
    dir: Path
    label: str
    tag: str
    version: str


@dataclass
class ContainerPublication:
    batch: dict[str, Any]
    manifest: str = ""
    builds: int = 0
    digest: str | None = None
    is_published: bool = True


class ReleaseFixture(CliFixture):
    def seed(self) -> None:
        self.write("airlock-targets.toml", MANIFEST)
        self.write_json("packages/util/package.json", {"name": "@zyplux/util", "version": "1.2.3"})
        self.write("apps/cerberus/pyproject.toml", '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\n')
        self.write_json("apps/cerberus/package.json", {"name": "zyplux-cerberus", "private": True, "version": "2.3.4"})
        self.write("containers/ci/Containerfile", 'FROM scratch\nLABEL org.opencontainers.image.version="3.4.5"\n')
        self.write(".changeset/README.md", "# Release notes\n")
        for directory, version, notes in (
            ("packages/util", "1.2.3", "Publish the reviewed utility changes."),
            ("apps/cerberus", "2.3.4", "Validate repository release contracts."),
            ("containers/ci", "3.4.5", "Refresh the CI container."),
        ):
            self.write(f"{directory}/CHANGELOG.md", f"# Releases\n\n## {version}\n\n### Patch Changes\n\n- {notes}\n")
        self.on("git rev-parse --show-toplevel", str(self.root))
        self.on("git rev-parse HEAD", "sha-head")
        self.on("git rev-parse origin/main", "sha-head")
        self.on("git fetch")
        self.on("git status --porcelain")
        self.on("gh repo view", "zyplux/zyplux")
        self.on("gh auth token", Reply(exit_code=1))
        self.on("gh api graphql", MISSING_RELEASE)
        self.on("gh release create")
        self.on(
            "gh release download", json.dumps({"image": f"ghcr.io/zyplux/ci@sha256:{'1' * 64}", "version": "3.4.5"})
        )
        self.on("pnpm version")
        self.on("pnpm install")
        self.on("uv version")
        self.on("uv lock")
        self.on("git ls-files", lambda call: list_sources(self, call))
        self.action_releases([])
        self.on("tar -xOf", lambda call: inspect_archive(self, call))
        self.on("pnpm list", lambda _: json.dumps(list_workspace_packages(self.root)))
        self.published()
        self.serve("https://registry.npmjs.org/util.tgz", Response())
        stage_packagers(self)

    def target(self, name: str = "util") -> Target:
        fields = {
            "util": ("packages/util", "@zyplux/util", "util-v1.2.3", "1.2.3"),
            "cerberus": ("apps/cerberus", "zyplux-cerberus", "cerberus-v2.3.4", "2.3.4"),
            "ci": ("containers/ci", "ghcr.io/zyplux/ci", "ci-image-v3.4.5", "3.4.5"),
        }
        directory, label, tag, version = fields[name]
        return Target(self.root / directory, label, tag, version)

    def published(self, *, npm: bool = False, pypi: bool = False, ghcr: bool = False) -> None:
        self.serve("https://ghcr.io/token", Response({"token": "gh-token"}))
        self.serve("https://ghcr.io/v2/", Response(status=200 if ghcr else 404))
        self.serve(
            "https://pypi.org/",
            Response(
                {"urls": [{"packagetype": "bdist_wheel"}, {"packagetype": "sdist"}]} if pypi else None,
                200 if pypi else 404,
            ),
        )
        for registry in ("https://registry.npmjs.org/", "https://npm.pkg.github.com/"):
            self.serve(
                registry,
                Response(
                    {"versions": {"1.2.3": {"dist": {"tarball": "https://registry.npmjs.org/util.tgz"}}}}
                    if npm
                    else None,
                    200 if npm else 404,
                ),
            )

    def all_published(self, *, pypi: bool = True) -> None:
        self.published(npm=True, pypi=pypi, ghcr=True)
        self.on("gh api graphql", PUBLISHED_RELEASE)

    def stage_npm(self, *, exit_code: int = 0) -> None:
        prepare_publication(self)

        def publish(_: Command) -> str | Reply:
            if exit_code:
                return Reply(exit_code=exit_code)
            self.published(npm=True)
            return ""

        self.on("pnpm publish", publish)

    def configure(self, kind: str, fields: str) -> None:
        sections = re.split(r"(?=^\[)", self.read("airlock-targets.toml"), flags=re.MULTILINE)
        index = next(index for index, section in enumerate(sections) if f'kind = "{kind}"' in section)
        lines = sections[index].splitlines()
        for declaration in fields.splitlines():
            key = declaration.split("=", 1)[0].strip()
            if key == "kind" and declaration in {'kind = "action"', 'kind = "ghcr"'}:
                lines = [line for line in lines if not line.startswith("requires =")]
            found = next((index for index, line in enumerate(lines) if line.lstrip().startswith(f"{key} =")), None)
            if found is None:
                lines.append(declaration)
            else:
                lines[found] = declaration
        sections[index] = "\n".join(lines) + "\n"
        self.write("airlock-targets.toml", "".join(sections))

    def plan(self, tag: str | None = None, *, error: str | None = None) -> list[dict[str, Any]]:
        execution = self.run("plan", *(["--tag", tag] if tag else []), error=error)
        return [] if error is not None else json.loads(execution.stdout.splitlines()[-1])["include"]

    def publish_batch(self, batch: dict[str, Any], *, error: str | None = None) -> None:
        self.run("publish", "--batch", json.dumps(batch), error=error)

    def expect_release(self, tag: str, commit: str = "sha-head") -> str:
        calls = self.matching(rf"^gh release create {re.escape(tag)} ")
        assert len(calls) == 1
        argv = calls[0].argv
        notes = argv[argv.index("--notes-file") + 1]
        assert argv == ["release", "create", tag, "--notes-file", notes, "--target", commit, "--title", tag]
        assert not Path(notes).parent.exists()
        return notes

    def expect_npm(self, directory: Path | None = None) -> None:
        directory = directory or self.target().dir
        packing = [call for call in self.matching("^pnpm pack") if call.cwd == str(directory)]
        assert len(packing) == 1
        archive = packing[0].argv[-1]
        assert self.matching(rf"^tar -xOf {re.escape(archive)} package/package.json$")
        uploading = [call for call in self.matching("^pnpm publish") if call.cwd == str(directory)]
        assert len(uploading) == 1
        assert uploading[0].argv == ["publish", archive, "--publish-wait-timeout", "0"]
        assert not Path(archive).parent.exists()

    def prepare_workspace(self) -> None:
        self.write_json(
            "package.json",
            {
                "name": "release-fixture",
                "packageManager": json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))[
                    "packageManager"
                ],
                "private": True,
            },
        )
        self.write_json("packages/util/package.json", {"name": "@zyplux/util", "private": True, "version": "1.2.3"})
        self.write(
            "pnpm-workspace.yaml",
            "packages:\n  - apps/*\n  - packages/*\nversioning:\n  changelog:\n    storage: repository\n",
        )
        self.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["apps/cerberus"]\n')
        self.write(
            "apps/cerberus/pyproject.toml",
            '[project]\nname = "zyplux-cerberus"\nversion = "2.3.4"\nrequires-python = ">=3.14"\n',
        )
        self.write(
            ".changeset/feature.md",
            '---\n"@zyplux/util": minor\n"zyplux-cerberus": patch\n---\n\nExpose reviewed target release notes.\n',
        )
        (self.root / "node_modules").symlink_to(REPO_ROOT / "node_modules", target_is_directory=True)
        self.on("pnpm", self.run_real)
        self.on("uv", self.run_real)
        stage_packagers(self)

    def action(self) -> None:
        self.write(
            "airlock-targets.toml",
            """scope = "@zyplux"
[setup-pm]
kind = "action"
label = "zyplux-setup-pm"
repository = "zyplux/zyplux"
version = { file = "apps/action-setup-pm/pyproject.toml", regex = '^version = "([^"]+)"' }
""",
        )
        self.write("apps/action-setup-pm/pyproject.toml", '[project]\nname = "zyplux-setup-pm"\nversion = "1.0.0"\n')
        self.write_json(
            "apps/action-setup-pm/package.json", {"name": "zyplux-setup-pm", "private": True, "version": "1.0.0"}
        )
        self.write("apps/action-setup-pm/CHANGELOG.md", "# Releases\n\n## 1.0.0\n\n- Cache package managers.\n")
        self.on("git rev-parse HEAD", "reviewed-sha")
        self.on("gh api graphql", '{"data":{"repository":{"release":{"id":"release-id"}}}}')
        self.on("git ls-remote origin refs/tags/setup-pm-v1", "old-sha\trefs/tags/setup-pm-v1")
        self.on("git ls-remote origin refs/tags/setup-pm-v1.0.0*", "release-sha\trefs/tags/setup-pm-v1.0.0")
        self.on("git rev-parse FETCH_HEAD^{commit}", "release-sha")
        self.on("git push")
        self.action_releases([build_release("setup-pm-v1.0.0")])
        prepare_publication(self)

    def action_releases(self, *pages: list[dict[str, Any]]) -> None:
        self.on("gh api --paginate --slurp", json.dumps(pages))

    def container(self) -> dict[str, Any]:
        prepare_publication(self)
        self.env.update(GH_TOKEN=self.credential, GITHUB_ACTOR="publisher")
        self.on("git rev-parse HEAD", "reviewed-sha")
        self.published()
        batch = self.plan(self.target("ci").tag)[0]
        self.on("podman")
        self.on("gh release upload")
        self.on("gh release edit")
        return batch

    def use_package(self) -> None:
        self.write("airlock-targets.toml", PACKAGE_MANIFEST)
        self.on(f"git -C {self.root} ls-tree")
        self.published_version("1.2.3")

    def published_version(self, version: str | None = None) -> None:
        for registry in ("https://registry.npmjs.org/", "https://npm.pkg.github.com/"):
            self.serve(
                registry, Response({"dist-tags": {"latest": version}} if version else None, 200 if version else 404)
            )
        self.serve(
            "https://pypi.org/", Response({"info": {"version": version}} if version else None, 200 if version else 404)
        )
        self.serve("https://ghcr.io/token", Response({"token": "image-token"}))
        self.serve("https://ghcr.io/v2/", Response({"tags": [] if version is None else [version]}))
        self.action_releases([] if version is None else [build_release(f"util-v{version}")])

    def base_version(self, version: str | None = None) -> None:
        self.on(
            f"git -C {self.root} ls-tree --name-only origin/main -- airlock-targets.toml",
            "airlock-targets.toml" if version else "",
        )
        self.on(f"git -C {self.root} show origin/main:airlock-targets.toml", self.read("airlock-targets.toml"))
        self.on(
            f"git -C {self.root} ls-tree --name-only origin/main -- packages/util/package.json",
            "packages/util/package.json",
        )
        self.on(f"git -C {self.root} show origin/main:packages/util/package.json", json.dumps({"version": version}))

    def publish(self, tag: str, *, error: str | None = None) -> subprocess.CompletedProcess[str]:
        name = tag.rsplit("-v", 1)[0]
        spec = tomllib.loads(self.read("airlock-targets.toml"))[name]
        return self.run(
            "publish",
            "--batch",
            json.dumps({
                "environment": spec.get("environment", "actions" if spec["kind"] == "action" else spec["kind"]),
                "id": f"{spec['kind']}-{name}",
                "kind": spec["kind"],
                "runner": "ubuntu-latest",
                "tags": [tag],
            }),
            error=error,
        )

    def consumer(self) -> Target:
        extra = ""
        for name in ("consumer", "independent"):
            extra += (
                f'[{name}]\nkind = "npm"\nversion = {{ file = "packages/{name}/package.json", json = "version" }}\n'
            )
            manifest: dict[str, Any] = {"name": f"@zyplux/{name}", "version": "1.2.3"}
            if name == "consumer":
                manifest["dependencies"] = {"@zyplux/util": "^1.2.0"}
            self.write_json(f"packages/{name}/package.json", manifest)
            self.write(f"packages/{name}/CHANGELOG.md", f"# {name}\n\n## 1.2.3\n\n- Publish {name}.\n")
        self.write("airlock-targets.toml", self.read("airlock-targets.toml").replace("[util]", extra + "[util]"))
        prepare_publication(self)
        return Target(self.root / "packages/consumer", "@zyplux/consumer", "consumer-v1.2.3", "1.2.3")

    def bundled_consumer(self) -> Target:
        consumer = self.consumer()
        self.write_json("package.json", {"name": "release-fixture", "private": True, "version": "0.0.0"})
        self.write("pnpm-workspace.yaml", "packages:\n  - packages/*\n")
        self.write_json(
            "packages/implementation/package.json",
            {"name": "@zyplux/implementation", "private": True, "version": "1.0.0"},
        )
        self.write_json(
            "packages/consumer/package.json",
            {
                "name": consumer.label,
                "version": consumer.version,
                "dependencies": {"@zyplux/implementation": "workspace:*"},
            },
        )
        self.write(
            ".pnpmfile.mjs",
            "export const hooks = { beforePacking(manifest) { "
            "delete manifest.dependencies?.['@zyplux/implementation']; return manifest; } };",
        )
        self.on("pnpm pack", self.run_real)
        self.on("tar -xOf", self.run_real)
        prepare_publication(self)
        return consumer


def prepare_publication(fixture: CliFixture) -> None:
    fixture.run("prepare")
    fixture.calls.clear()


def list_sources(fixture: ReleaseFixture, call: Command) -> str:
    directories = call.argv[call.argv.index("--") + 1 :]
    return "\0".join(
        path.relative_to(fixture.root).as_posix()
        for directory in directories
        for path in Path(directory).rglob("*")
        if path.is_file() or path.is_symlink()
    )


def inspect_archive(fixture: CliFixture, _call: Command) -> str:
    packing = next(call for call in reversed(fixture.calls) if call.program == "pnpm" and call.argv[0] == "pack")
    return (Path(packing.cwd) / "package.json").read_text(encoding="utf-8")


def list_workspace_packages(root: Path) -> list[dict[str, Any]]:
    return [
        {"private": False, **json.loads(file.read_text(encoding="utf-8")), "path": str(file.parent)}
        for file in (root / "packages").glob("*/package.json")
    ]


def capture_release_notes(fixture: ReleaseFixture) -> list[str]:
    notes: list[str] = []

    def capture(call: Command) -> str:
        notes.append(Path(call.argv[call.argv.index("--notes-file") + 1]).read_text(encoding="utf-8"))
        return ""

    fixture.on("gh release create", capture)
    return notes


@pytest.fixture
def release(tmp_path: Path) -> Iterator[ReleaseFixture]:
    fixture = ReleaseFixture(tmp_path)
    server, thread = fixture.start()
    fixture.seed()
    try:
        yield fixture
        assert not fixture.failures, "\n".join(fixture.failures)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def prepared_release(release: ReleaseFixture) -> None:
    prepare_publication(release)
