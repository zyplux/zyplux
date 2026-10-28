from __future__ import annotations

import tomllib
import zipfile
from typing import TYPE_CHECKING

import pytest
from archive_fixture import configure_python_package, hash_archives, stage_git, stage_packagers, write_tar, write_wheel
from cli_fixture import Reply

if TYPE_CHECKING:
    from pathlib import Path

    from release_fixture import ReleaseFixture


@pytest.mark.parametrize("kind", ["npm", "python"])
def test_25_1_1_ignores_archive_timestamps_ordering_and_compression(
    release: ReleaseFixture, tmp_path: Path, kind: str
) -> None:
    files = {"first.py": b"first", "second.py": b"second"}
    first, second = tmp_path / "first.whl", tmp_path / "second.whl"
    if kind == "python":
        write_wheel(first, files)
        write_wheel(
            second, dict(reversed(files.items())), timestamp=(2026, 1, 1, 0, 0, 0), compression=zipfile.ZIP_DEFLATED
        )
    else:
        first, second = tmp_path / "first.tgz", tmp_path / "second.tgz"
        write_tar(first, {f"first/{name}": contents for name, contents in files.items()})
        write_tar(
            second,
            {f"second/{name}": contents for name, contents in reversed(files.items())},
            mtime=100,
            compresslevel=1,
        )
    assert first.read_bytes() != second.read_bytes()
    assert hash_archives(release, [first]) == hash_archives(release, [second])


@pytest.mark.parametrize("change", ["contents", "added", "removed", "renamed", "executable", "metadata"])
def test_25_1_2_detects_packaged_files_permissions_and_metadata_changes(
    release: ReleaseFixture, tmp_path: Path, change: str
) -> None:
    files = {"package/index.js": b"source", "package/package.json": b'{"dependencies":{"other":"1"}}'}
    first, second = tmp_path / "first.tgz", tmp_path / "second.tgz"
    write_tar(first, files)
    match change:
        case "contents":
            files["package/index.js"] = b"changed"
        case "added":
            files["package/new.js"] = b"new"
        case "removed":
            del files["package/index.js"]
        case "renamed":
            files["package/renamed.js"] = files.pop("package/index.js")
        case "metadata":
            files["package/package.json"] = b'{"dependencies":{"other":"2"}}'
    write_tar(second, files, mode=0o755 if change == "executable" else 0o644)
    assert hash_archives(release, [first]) != hash_archives(release, [second])


def test_25_1_3_covers_both_python_distributions_and_ignores_their_listing_order(
    release: ReleaseFixture, tmp_path: Path
) -> None:
    wheel, source = tmp_path / "package.whl", tmp_path / "package.tar.gz"
    write_wheel(wheel, {"package/__init__.py": b"code"})
    write_tar(source, {"package/pyproject.toml": b"metadata"})
    fingerprint = hash_archives(release, [wheel, source])
    assert fingerprint == hash_archives(release, [source, wheel])
    write_tar(source, {"package/pyproject.toml": b"changed metadata"})
    assert fingerprint != hash_archives(release, [wheel, source])


@pytest.mark.parametrize("includes", [None, ["**/*"], ["**/*.js", "!**/internal/**"]])
def test_25_1_4_filters_archive_files_with_configured_includes(
    release: ReleaseFixture, tmp_path: Path, includes: list[str] | None
) -> None:
    archive = tmp_path / "package.tgz"
    files = {"package/index.js": b"code", "package/docs/README.md": b"original", "package/internal/cache.txt": b"one"}
    write_tar(archive, files)
    before = hash_archives(release, [archive], includes)
    files["package/docs/README.md"] = b"updated"
    files["package/internal/cache.txt"] = b"two" if includes is not None else b"one"
    write_tar(archive, files)
    after = hash_archives(release, [archive], includes)
    assert (before != after) == (includes == ["**/*"])


@pytest.mark.parametrize("includes", [None, ["**/*"]])
def test_25_1_5_filters_readme_descriptions_and_derived_wheel_checksums(
    release: ReleaseFixture, tmp_path: Path, includes: list[str] | None
) -> None:
    wheel = tmp_path / "package.whl"
    fingerprints = []
    for readme in ("Original README", "Updated README"):
        metadata = (
            "Metadata-Version: 2.4\nName: zyplux-util\nVersion: 1.2.3\n"
            f"Description-Content-Type: text/markdown\n\n{readme}\n"
        ).encode()
        write_wheel(
            wheel,
            {
                "package/__init__.py": b"code",
                "README.md": readme.encode(),
                "package.dist-info/METADATA": metadata,
                "package.dist-info/RECORD": readme.encode(),
            },
        )
        fingerprints.append(hash_archives(release, [wheel], includes))
    assert (fingerprints[0] != fingerprints[1]) == (includes == ["**/*"])


def test_25_2_1_initializes_all_target_hashes_and_preserves_manifest_comments(release: ReleaseFixture) -> None:
    stage_packagers(release)
    release.write("airlock_targets.toml", "# Release configuration\n" + release.read("airlock_targets.toml"))
    release.run("prepare")
    manifest = tomllib.loads(release.read("airlock_targets.toml"))
    for name in ("util", "cerberus", "ci-image"):
        assert manifest[name]["hash"].startswith("sha256:")
        assert "includes" not in manifest[name]
    assert release.read("airlock_targets.toml").startswith("# Release configuration\n")
    assert not release.matching(r"^gh\b|^(pnpm|uv) publish\b")
    prepared = release.read("airlock_targets.toml")
    release.run("prepare")
    assert release.read("airlock_targets.toml") == prepared


@pytest.mark.parametrize("kind", ["npm", "pypi"])
def test_25_2_2_rejects_stale_hashes_before_publishing(release: ReleaseFixture, kind: str) -> None:
    stage_packagers(release)
    release.run("prepare")
    target = release.target("util" if kind == "npm" else "cerberus")
    (target.dir / "changed.py").write_text("changed")
    release.publish(target.tag, error="release contents differ from hash")
    assert not release.matching("pnpm publish|uv publish|gh release create")


def test_25_2_3_leaves_the_manifest_unchanged_when_packaging_fails(release: ReleaseFixture) -> None:
    stage_packagers(release)
    manifest = release.read("airlock_targets.toml")
    release.on("uv build", Reply(stderr="Build failed", exit_code=1))
    release.run("prepare", error="Build failed")
    assert release.read("airlock_targets.toml") == manifest


def test_25_2_4_rejects_invalid_hash_formats(release: ReleaseFixture) -> None:
    release.configure("npm", 'hash = "sha256:invalid"')
    release.run("plan", error="String should match pattern")


def test_25_2_5_rejects_empty_package_builds(release: ReleaseFixture) -> None:
    release.use_package()
    configure_python_package(release)
    release.on("uv build")
    release.run("prepare", error="produced no archives")


def test_25_2_6_refreshes_hashes_after_versioning_and_keeps_repeated_preparation_stable(
    release: ReleaseFixture,
) -> None:
    stage_packagers(release)
    release.run("prepare")
    previous = tomllib.loads(release.read("airlock_targets.toml"))
    release.prepare_workspace()
    stage_packagers(release)
    release.run("prepare")
    prepared = tomllib.loads(release.read("airlock_targets.toml"))
    assert all(prepared[name]["hash"] != previous[name]["hash"] for name in ("util", "cerberus"))
    release.run("prepare")
    assert tomllib.loads(release.read("airlock_targets.toml")) == prepared


@pytest.mark.parametrize("kind", ["npm", "pypi", "action", "ghcr"])
def test_25_2_7_rejects_missing_fingerprints_before_publication(release: ReleaseFixture, kind: str) -> None:
    if kind == "action":
        release.action()
        manifest = release.read("airlock_targets.toml")
        release.write(
            "airlock_targets.toml",
            "\n".join(line for line in manifest.splitlines() if not line.startswith("hash")),
        )
        tag = "setup-pm-v1.0.0"
    else:
        tag = release.target({"npm": "util", "pypi": "cerberus", "ghcr": "ci"}[kind]).tag
    release.publish(tag, error="missing hash; run airlock prepare")
    assert not release.matching("pnpm publish|uv publish|podman build|gh release create|git push")


@pytest.mark.parametrize("kind", ["npm", "pypi"])
@pytest.mark.parametrize("problem", ["missing", "stale"])
def test_25_2_8_validates_package_fingerprints_before_repairing_github_releases(
    release: ReleaseFixture, kind: str, problem: str
) -> None:
    release.run("prepare")
    release.calls.clear()
    release.published(npm=True, pypi=True)
    target = release.target("util" if kind == "npm" else "cerberus")
    if problem == "missing":
        release.write(
            "airlock_targets.toml",
            "\n".join(
                line for line in release.read("airlock_targets.toml").splitlines() if not line.startswith("hash")
            ),
        )
        error = "missing hash"
    else:
        (target.dir / "changed.py").write_text("changed release contents")
        error = "release contents differ from hash"
    release.publish(target.tag, error=error)
    assert not release.matching("pnpm publish|uv publish|gh release create")


@pytest.mark.parametrize("kind", ["npm", "pypi"])
def test_25_2_9_builds_each_package_once_when_repairing_a_github_release(release: ReleaseFixture, kind: str) -> None:
    release.run("prepare")
    release.calls.clear()
    release.published(npm=True, pypi=True)
    release.publish(release.target("util" if kind == "npm" else "cerberus").tag)
    assert len(release.matching("pnpm pack|uv build")) == 1
    assert not release.matching("pnpm publish|uv publish")


@pytest.mark.parametrize("kind", ["npm", "pypi"])
def test_25_2_10_rejects_stale_prepared_dependencies_before_upload(release: ReleaseFixture, kind: str) -> None:
    release.run("prepare")
    release.configure(kind, 'depends_on = ["unknown"]')
    release.publish(
        release.target("util" if kind == "npm" else "cerberus").tag,
        error="prepared dependencies differ from package contents",
    )
    assert not release.matching("pnpm publish|uv publish|gh release create")


@pytest.mark.parametrize("kind", ["npm", "pypi"])
def test_25_2_11_rejects_root_package_archives_that_include_the_release_manifest(
    release: ReleaseFixture, kind: str
) -> None:
    release.use_package()
    release.write_json("package.json", {"name": "zyplux-util", "version": "1.2.3"})
    release.write("CHANGELOG.md", "## 1.2.3\n\n- Publish utility.\n")
    release.configure("npm", f'kind = "{kind}"\nmanifest = "package.json"')
    release.write("pyproject.toml", '[project]\nname = "zyplux-util"\nversion = "1.2.3"\n')
    manifest = release.read("airlock_targets.toml")
    execution = release.run("prepare", error="package archives must exclude airlock_targets.toml")
    assert release.read("airlock_targets.toml") == manifest
    assert "Traceback" not in execution.stderr
    assert not release.matching("pnpm publish|uv publish|gh release create")


def test_25_3_1_detects_bundled_shared_changes_and_ignores_unpacked_files(release: ReleaseFixture) -> None:
    release.use_package()
    release.write_json(
        "packages/util/package.json",
        {"name": "@zyplux/util", "version": "1.2.3", "files": ["dist"], "scripts": {"prepack": "node build.cjs"}},
    )
    release.write(
        "packages/util/build.cjs",
        "const fs = require('node:fs');\n"
        "fs.mkdirSync('dist', {recursive: true});\n"
        "fs.copyFileSync('../../shared/schema.js', 'dist/index.js');\n",
    )
    release.write("shared/schema.js", "export const required = true;\n")
    release.on("pnpm pack", release.run_real)
    release.run("prepare")
    baseline = tomllib.loads(release.read("airlock_targets.toml"))["util"]["hash"]
    release.write("packages/util/tests/example.js", "development-only file")
    release.run("prepare")
    assert tomllib.loads(release.read("airlock_targets.toml"))["util"]["hash"] == baseline
    release.write("shared/schema.js", "export const required = false;\n")
    release.run("prepare")
    assert tomllib.loads(release.read("airlock_targets.toml"))["util"]["hash"] != baseline


@pytest.mark.parametrize("directory", ["apps/action-setup-pm", "actions/setup"])
def test_25_4_1_covers_implicit_and_explicit_action_sources(release: ReleaseFixture, directory: str) -> None:
    release.action()
    if directory == "actions/setup":
        release.configure("action", 'includes = ["actions/setup/**", "!**/*.md", "!**/*.markdown"]')
    excluded = "shared/unrelated.py" if directory == "apps/action-setup-pm" else "apps/action-setup-pm/src/setup.py"
    release.write(f"{directory}/action.yml", "name: Setup\n")
    release.write(excluded, "print('unselected source')\n")
    release.write(".gitignore", "**/__pycache__/\n")
    stage_git(release)
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    release.write(f"{directory}/__pycache__/setup.pyc", "generated")
    release.write(excluded, "print('changed unselected source')\n")
    release.write("docs/unrelated.md", "unrelated")
    release.run("prepare")
    assert release.read("airlock_targets.toml") == baseline
    release.write(f"{directory}/action.yml", "name: Changed setup\n")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != baseline


@pytest.mark.parametrize("kind", ["action", "ghcr"])
@pytest.mark.parametrize("has_markdown", [False, True])
def test_25_4_16_applies_markdown_selection_to_action_and_container_inputs(
    release: ReleaseFixture, kind: str, *, has_markdown: bool
) -> None:
    if kind == "action":
        release.action()
    if has_markdown:
        release.configure(kind, 'includes = ["**/*"]')
    directory = "apps/action-setup-pm" if kind == "action" else "containers/ci"
    release.write(f"{directory}/README.md", "Original documentation")
    stage_git(release)
    release.run("prepare")
    manifest = release.read("airlock_targets.toml")
    release.write(f"{directory}/README.md", "Updated documentation")
    release.run("prepare")
    assert (release.read("airlock_targets.toml") != manifest) == has_markdown


@pytest.mark.parametrize("ignorefile", [".dockerignore", ".containerignore"])
def test_25_4_2_covers_container_inputs_using_build_ignore_rules(release: ReleaseFixture, ignorefile: str) -> None:
    stage_packagers(release)
    stage_git(release)
    release.configure("ghcr", 'build_context = "."\ndockerfile = "containers/ci/Containerfile"')
    release.write(".dockerignore", "src\n")
    release.write(ignorefile, ".git\ndocs\n!docs/include.txt\n*.tmp\nscratch\n")
    release.write(".gitignore", "scratch/\n")
    release.write("src/app.js", "source")
    release.write("docs/include.txt", "included")
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    release.write("docs/ignored.md", "documentation")
    release.write("scratch/local.txt", "local cache")
    release.write("unused.tmp", "temporary file")
    release.run("prepare")
    assert release.read("airlock_targets.toml") == baseline
    release.write("docs/include.txt", "changed included content")
    release.run("prepare")
    included = release.read("airlock_targets.toml")
    assert included != baseline
    release.write("src/app.js", "changed source")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != included
    source = release.read("airlock_targets.toml")
    release.write("containers/ci/Containerfile", release.read("containers/ci/Containerfile") + "# Changed recipe\n")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != source


@pytest.mark.parametrize("kind", ["action", "ghcr"])
def test_25_4_3_rejects_stale_action_and_container_fingerprints_before_publication(
    release: ReleaseFixture, kind: str
) -> None:
    stage_packagers(release)
    if kind == "action":
        release.action()
        path, tag = "apps/action-setup-pm/action.yml", "setup-pm-v1.0.0"
    else:
        path, tag = "containers/ci/Containerfile", "ci-image-v3.4.5"
    release.run("prepare")
    previous = (release.root / path).read_text() if (release.root / path).is_file() else ""
    release.write(path, previous + "\n# Changed source\n")
    reason = "build-input fingerprint" if kind == "ghcr" else "release contents differ from hash"
    release.publish(tag, error=reason)
    assert not release.matching("podman build|gh release create|git push")


@pytest.mark.parametrize("kind", ["npm", "pypi", "ghcr"])
def test_25_4_4_rejects_manual_surface_declarations(release: ReleaseFixture, kind: str) -> None:
    release.configure(kind, 'surface = ["src"]')
    release.run("plan", error="Unrecognized key")


@pytest.mark.parametrize("path", ["../outside", "/outside"])
def test_25_4_5_rejects_action_path_declarations(release: ReleaseFixture, path: str) -> None:
    release.action()
    release.configure("action", f'path = "{path}"')
    release.run("prepare", error="Unrecognized key")


@pytest.mark.parametrize("kind", ["action", "ghcr"])
@pytest.mark.parametrize("link_kind", ["file", "directory", "broken"])
def test_25_4_6_hashes_symlink_identity_including_directory_and_broken_links(
    release: ReleaseFixture, kind: str, link_kind: str
) -> None:
    if kind == "action":
        release.action()
        directory = release.root / "apps/action-setup-pm"
    else:
        directory = release.target("ci").dir
    for name in ("first", "second"):
        if link_kind != "broken":
            path = f"shared/{name}/item.txt" if link_kind == "directory" else f"shared/{name}"
            release.write(path, "identical contents")
    link = directory / "linked-input"
    link.symlink_to("../../shared/first", target_is_directory=link_kind == "directory")
    stage_git(release)
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    link.unlink()
    link.symlink_to("../../shared/second", target_is_directory=link_kind == "directory")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != baseline


@pytest.mark.parametrize("file", ["pyproject.toml", "uv.lock"])
def test_25_4_7_selects_individual_files_outside_the_action_directory_with_includes(
    release: ReleaseFixture, file: str
) -> None:
    release.action()
    release.write("pyproject.toml", "[project]\n")
    release.write("uv.lock", "version = 1\n")
    release.configure("action", 'includes = ["apps/action-setup-pm/**", "pyproject.toml", "uv.lock"]')
    release.run("prepare")
    release.write(file, release.read(file) + "\n# Changed installation input.\n")
    release.publish("setup-pm-v1.0.0", error="release contents differ from hash")
    assert not release.matching("gh release create|git push")


@pytest.mark.parametrize("pattern", ["/etc/hosts", "../../../outside.lock"])
def test_25_4_8_rejects_action_includes_outside_the_repository(release: ReleaseFixture, pattern: str) -> None:
    release.action()
    release.configure("action", f'includes = ["{pattern}"]')
    release.run("prepare", error="Action includes must stay within the repository")


@pytest.mark.parametrize("selection", ["dockerfile", "build_context"])
def test_25_4_9_covers_container_build_configuration_with_identical_input_files(
    release: ReleaseFixture, selection: str
) -> None:
    release.write("containers/ci/Alternative", "FROM scratch\n")
    release.configure("ghcr", 'build_context = "containers"\ndockerfile = "containers/ci/Containerfile"')
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    declaration = (
        'dockerfile = "containers/ci/Alternative"' if selection == "dockerfile" else 'build_context = "containers/ci"'
    )
    release.configure("ghcr", declaration)
    release.publish("ci-image-v3.4.5", error="build-input fingerprint")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != baseline
    assert not release.matching("podman build|gh release create")


@pytest.mark.parametrize("change", ["retarget", "contents"])
def test_25_4_10_fingerprints_selected_symlinks_and_selected_target_files(release: ReleaseFixture, change: str) -> None:
    release.action()
    directory = "apps/action-setup-pm" if change == "retarget" else "shared"
    for name in ("first", "second"):
        release.write(f"{directory}/{name}.lock", name)
    link = release.root / "runtime.lock"
    link.symlink_to(f"{directory}/first.lock")
    release.configure("action", 'includes = ["apps/action-setup-pm/**", "runtime.lock", "shared/*.lock"]')
    release.run("prepare")
    if change == "retarget":
        link.unlink()
        link.symlink_to(f"{directory}/second.lock")
    else:
        release.write(f"{directory}/first.lock", "changed runtime dependency")
    release.publish("setup-pm-v1.0.0", error="release contents differ from hash")
    assert not release.matching("gh release create|git push")


@pytest.mark.parametrize("change", ["source", "patch", "minor", "major", "lockfile", "root_manifest"])
def test_25_4_17_fingerprints_configured_runtime_major_and_minor_versions_only(
    release: ReleaseFixture, change: str
) -> None:
    release.action()
    release.write("apps/airlock/pyproject.toml", '[project]\nname = "zyplux-airlock"\nversion = "2.2.0"\n')
    release.write_json("apps/airlock/package.json", {"name": "zyplux-airlock", "version": "2.2.0", "private": True})
    release.write("apps/airlock/CHANGELOG.md", "# Airlock\n\n## 2.2.0\n\n- Prepare releases.\n")
    release.write("apps/airlock/src/airlock.py", "print('release')\n")
    release.write(
        "airlock_targets.toml",
        release.read("airlock_targets.toml") + '\n[airlock]\nmanifest = "apps/airlock/pyproject.toml"\n',
    )
    release.configure(
        "action",
        'manifest = "apps/airlock/pyproject.toml"\n'
        'includes = ["apps/action-setup-pm/**", "!**/*.md", "!**/*.markdown"]\n'
        'sync_minor_from = "airlock"',
    )
    release.run("prepare")
    baseline = tomllib.loads(release.read("airlock_targets.toml"))["setup-pm"]
    assert baseline["sync_minor_from"] == "airlock"
    if change in {"patch", "minor", "major"}:
        version = {"patch": "2.2.1", "minor": "2.3.0", "major": "3.0.0"}[change]
        for filename in ("pyproject.toml", "package.json", "CHANGELOG.md"):
            path = f"apps/airlock/{filename}"
            release.write(path, release.read(path).replace("2.2.0", version))
    else:
        path = {"source": "apps/airlock/src/airlock.py", "lockfile": "uv.lock", "root_manifest": "pyproject.toml"}[
            change
        ]
        release.write(path, "# Changed input\n")
    release.run("prepare")
    updated = tomllib.loads(release.read("airlock_targets.toml"))["setup-pm"]
    assert updated["sync_minor_from"] == "airlock"
    assert (updated["hash"] != baseline["hash"]) == (change in {"minor", "major"})


def test_25_4_18_rejects_unknown_minor_version_sources(release: ReleaseFixture) -> None:
    release.action()
    release.configure("action", 'sync_minor_from = "missing"')
    release.run("prepare", error="unknown sync_minor_from target: missing")


@pytest.mark.parametrize("selection", ["default", "explicit", "directory"])
def test_25_4_11_rejects_missing_container_dockerfiles_while_preparing(release: ReleaseFixture, selection: str) -> None:
    release.write_json("containers/ci/package.json", {"name": "ci-image", "version": "3.4.5"})
    release.configure("ghcr", 'manifest = "containers/ci/package.json"')
    if selection == "default":
        (release.target("ci").dir / "Containerfile").unlink()
    else:
        release.configure("ghcr", 'dockerfile = "containers/ci/recipe"')
        if selection == "directory":
            (release.target("ci").dir / "recipe").mkdir()
    manifest = release.read("airlock_targets.toml")
    release.run("prepare", error="Dockerfile must exist as a regular file")
    assert release.read("airlock_targets.toml") == manifest
    assert not release.matching("podman build|gh release create")


def test_25_4_12_fingerprints_git_ignored_container_inputs(release: ReleaseFixture) -> None:
    stage_git(release)
    release.configure("ghcr", 'build_context = "."\ndockerfile = "containers/ci/Containerfile"')
    release.write(".dockerignore", ".git\n")
    release.write(".gitignore", "scratch/\n")
    release.write("scratch/settings.json", '{"enabled":true}')
    release.run("prepare")
    release.calls.clear()
    release.write("scratch/settings.json", '{"enabled":false}')
    release.publish("ci-image-v3.4.5", error="build-input fingerprint")
    assert not release.matching("git ls-files|podman build|gh release create")


@pytest.mark.parametrize("ignorefile", [".dockerignore", ".containerignore"])
def test_25_4_13_prefers_dockerfile_adjacent_ignore_rules_and_fingerprints_the_rules(
    release: ReleaseFixture, ignorefile: str
) -> None:
    release.configure("ghcr", 'build_context = "."\ndockerfile = "containers/ci/Containerfile"')
    release.write(".containerignore", "src\n")
    selected = f"containers/ci/{ignorefile}"
    rules = f"docs\n{selected}\n"
    release.write(selected, rules)
    release.write("src/app.js", "source")
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    release.write("docs/ignored.txt", "documentation")
    release.run("prepare")
    assert release.read("airlock_targets.toml") == baseline
    release.write("src/app.js", "changed source")
    release.run("prepare")
    source = release.read("airlock_targets.toml")
    assert source != baseline
    release.write(selected, rules + "*.cache\n")
    release.run("prepare")
    assert release.read("airlock_targets.toml") != source


@pytest.mark.parametrize("has_ignorefile", [True, False])
def test_25_4_14_reports_selected_container_inputs_on_fingerprint_mismatch(
    release: ReleaseFixture, *, has_ignorefile: bool
) -> None:
    release.configure("ghcr", 'build_context = "."\ndockerfile = "containers/ci/Containerfile"')
    if has_ignorefile:
        release.write("containers/ci/.dockerignore", "docs\n")
    release.run("prepare")
    release.write("src/app.js", "changed source")
    execution = release.publish("ci-image-v3.4.5", error="build-input fingerprint")
    message = execution.stdout + execution.stderr
    assert "build context: ." in message
    assert "Dockerfile: containers/ci/Containerfile" in message
    assert f"ignore file: {'containers/ci/.dockerignore' if has_ignorefile else 'none'}" in message


@pytest.mark.parametrize("metadata_path", [".git/HEAD", ".git"])
def test_25_4_15_requires_container_ignore_rules_to_exclude_git_metadata(
    release: ReleaseFixture, metadata_path: str
) -> None:
    release.configure("ghcr", 'build_context = "."\ndockerfile = "containers/ci/Containerfile"')
    release.write(metadata_path, "initial Git metadata\n")
    manifest = release.read("airlock_targets.toml")
    release.run("prepare", error="container build context includes Git metadata; exclude .git")
    assert release.read("airlock_targets.toml") == manifest
    release.write("containers/ci/.dockerignore", ".git\n")
    release.run("prepare")
    baseline = release.read("airlock_targets.toml")
    release.write(metadata_path, "changed Git metadata\n")
    release.run("prepare")
    assert release.read("airlock_targets.toml") == baseline
