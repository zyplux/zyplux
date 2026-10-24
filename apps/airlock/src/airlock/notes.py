from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from airlock import proc
from airlock.contracts import PythonTracking
from airlock.registries import load_npm_registry
from airlock.targets import load_targets

if TYPE_CHECKING:
    from airlock.contracts import ReleaseTarget


def load_release_notes(directory: Path, version: str) -> str:
    changelog = directory / "CHANGELOG.md"
    markdown = changelog.read_text(encoding="utf-8")
    lines = markdown.splitlines()
    headings = [
        token
        for token in MarkdownIt().parse(markdown)
        if token.type == "heading_open" and token.level == 0 and token.tag in {"h1", "h2"} and token.map
    ]
    section = next((heading for heading in headings if heading.map and lines[heading.map[0]] == f"## {version}"), None)
    if section is None or section.map is None:
        msg = f"no release notes for {version}; run pnpm release:prepare"
        raise ValueError(msg)
    next_heading = next((heading for heading in headings if heading.map and heading.map[0] > section.map[0]), None)
    end = next_heading.map[0] if next_heading and next_heading.map else len(lines)
    notes = "\n".join(lines[section.map[1] : end]).strip()
    document = SyntaxTreeNode(MarkdownIt().parse(notes))
    if not any(
        node.type in {"bullet_list", "ordered_list"} and node.children[0].children for node in document.children
    ):
        msg = f"{changelog}: release {version} has no changelog entries"
        raise ValueError(msg)
    return notes


def load_python_version(target: ReleaseTarget) -> str:
    manifest = target.directory / "package.json"
    tracking = PythonTracking.model_validate_json(manifest.read_text(encoding="utf-8"))
    if tracking.name != target.spec.label:
        msg = f"{manifest}: expected Python release target {target.spec.label}"
        raise ValueError(msg)
    return tracking.version


def validate_python_versions(targets: list[ReleaseTarget]) -> None:
    for target in targets:
        if Path(target.spec.version.file).name == "pyproject.toml" and load_python_version(target) != target.version:
            msg = f"{target.spec.label}: package.json and pyproject.toml versions must match"
            raise ValueError(msg)


def validate_consumed_intents() -> None:
    root = proc.find_root()
    pending = sorted(
        str(file.relative_to(root)) for file in (root / ".changeset").glob("*.md") if file.name != "README.md"
    )
    if pending:
        msg = f"Unconsumed change intents: {', '.join(pending)}; run pnpm release:prepare"
        raise ValueError(msg)


def load_prepared_targets(selected: list[ReleaseTarget] | None = None) -> list[tuple[ReleaseTarget, str]]:
    validate_consumed_intents()
    targets = load_targets() if selected is None else selected
    validate_python_versions(targets)
    return [(target, load_release_notes(target.directory, target.version)) for target in targets]


def prepare_release() -> None:
    root = proc.find_root()
    targets = load_targets(root)
    validate_python_versions(targets)
    registries: dict[str, str] = {}
    for target in targets:
        if target.spec.kind != "npm":
            continue
        key = f"{target.spec.label.split('/', 1)[0]}:registry" if target.spec.label.startswith("@") else "registry"
        registry = load_npm_registry(target.directory, target.spec.label)
        if key in registries and registries[key] != registry:
            msg = f"native pnpm preparation requires one publication registry per scope ({key})"
            raise ValueError(msg)
        registries[key] = registry
    proc.run(
        "pnpm",
        "version",
        "-r",
        "--no-git-checks",
        *(f"--config.{key}={registry}" for key, registry in registries.items()),
        cwd=root,
    )
    python_targets = [target for target in targets if Path(target.spec.version.file).name == "pyproject.toml"]
    for target in python_targets:
        proc.run("uv", "version", "--package", target.spec.label, "--frozen", load_python_version(target), cwd=root)
    proc.run("pnpm", "install", "--lockfile-only", cwd=root)
    if python_targets:
        proc.run("uv", "lock", cwd=root)
    load_prepared_targets()
