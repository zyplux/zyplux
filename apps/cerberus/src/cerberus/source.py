from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Protocol

from cerberus import gh, proc
from cerberus.config import Config
from cerberus.model import Repo

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_GITHUB_HOST = re.compile(r"^(?:git@)?github\.com[/:]", re.IGNORECASE)


def parse_org_ref(value: str) -> str:
    """Extract a GitHub org login from a bare name, `github.com/org`, or a URL.

    Accepts `zyplux`, `github.com/zyplux`, `https://github.com/zyplux/`, and
    `git@github.com:zyplux`. Rejects other hosts and empty input.
    """
    ref = _SCHEME.sub("", value.strip())
    ref = _GITHUB_HOST.sub("", ref)
    org = ref.strip("/").split("/", 1)[0]
    if not org or "." in org or ":" in org:
        raise ValueError(f"could not read a GitHub org from {value!r}")
    return org


class ControlPlaneUnavailable(RuntimeError):
    """A checkout-only source was asked for GitHub org/admin state it cannot reach."""


class RepoSource(Protocol):
    """Where a check reads a repo's facts from: the GitHub API, or a local checkout."""

    def repos(self) -> list[Repo]: ...
    def file(self, repo: Repo, path: str) -> str | None: ...
    def list_paths(self, repo: Repo) -> list[str]: ...
    def write_file(self, repo: Repo, path: str, content: str) -> None: ...
    def workflows(self, repo: Repo) -> dict[str, str]: ...
    def branch_rules(self, repo: Repo) -> list[dict[str, Any]]: ...
    def repo_secrets(self, repo: Repo) -> set[str]: ...
    def org_secrets(self) -> dict[str, str]: ...
    def org_secret_selected_repos(self, name: str) -> set[str]: ...
    def ruleset_active(self, name: str) -> bool: ...


class GitHubSource:
    """Reads every governed repo in an org through the GitHub CLI."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def org(self) -> str:
        return self._config.org

    def repos(self) -> list[Repo]:
        out: list[Repo] = []
        for raw in gh.list_repos(self.org):
            if raw["name"] in self._config.exclude_repos or raw.get("isFork"):
                continue
            branch = (raw.get("defaultBranchRef") or {}).get("name") or "main"
            out.append(
                Repo(
                    name=raw["name"],
                    owner=self.org,
                    default_branch=branch,
                    visibility=str(raw["visibility"]).lower(),
                )
            )
        return sorted(out, key=lambda r: r.name)

    def file(self, repo: Repo, path: str) -> str | None:
        return gh.raw_file(repo.owner, repo.name, path)

    def list_paths(self, repo: Repo) -> list[str]:
        ref = f"repos/{repo.full_name}/git/trees/{repo.default_branch}?recursive=1"
        try:
            tree = gh.api(ref) or {}
        except gh.GhError:
            return []
        entries = tree.get("tree", []) if isinstance(tree, dict) else []
        return [
            entry["path"]
            for entry in entries
            if entry.get("type") == "blob" and isinstance(entry.get("path"), str)
        ]

    def write_file(self, repo: Repo, path: str, content: str) -> None:
        raise NotImplementedError("the org scan is read-only; --fix runs only on a local checkout")

    def workflows(self, repo: Repo) -> dict[str, str]:
        try:
            entries = gh.api(f"repos/{repo.full_name}/contents/.github/workflows") or []
        except gh.GhError:
            return {}
        out: dict[str, str] = {}
        for entry in entries:
            name = entry.get("name", "")
            if entry.get("type") == "file" and name.endswith((".yml", ".yaml")):
                content = gh.raw_file(repo.owner, repo.name, entry["path"])
                if content is not None:
                    out[name] = content
        return out

    def branch_rules(self, repo: Repo) -> list[dict[str, Any]]:
        try:
            return gh.api(f"repos/{repo.full_name}/rules/branches/{repo.default_branch}") or []
        except gh.GhError:
            return []

    def repo_secrets(self, repo: Repo) -> set[str]:
        try:
            data = gh.api(f"repos/{repo.full_name}/actions/secrets") or {}
        except gh.GhError:
            return set()
        return {s["name"] for s in data.get("secrets", [])}

    def org_secrets(self) -> dict[str, str]:
        try:
            data = gh.api(f"orgs/{self.org}/actions/secrets") or {}
        except gh.GhError:
            return {}
        return {s["name"]: s.get("visibility", "all") for s in data.get("secrets", [])}

    def org_secret_selected_repos(self, name: str) -> set[str]:
        try:
            data = gh.api(f"orgs/{self.org}/actions/secrets/{name}/repositories") or {}
        except gh.GhError:
            return set()
        return {r["name"] for r in data.get("repositories", [])}

    def ruleset_active(self, name: str) -> bool:
        try:
            rulesets = gh.api(f"orgs/{self.org}/rulesets") or []
        except gh.GhError:
            return False
        return any(r.get("name") == name and r.get("enforcement") == "active" for r in rulesets)


class LocalSource:
    """Reads a single repo from a working-tree checkout on disk.

    Content lives in the checkout; GitHub control-plane state (rulesets, secret
    provisioning) does not, so those reads raise ControlPlaneUnavailable and the
    runner skips control-plane checks in this mode.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def _identity(self) -> tuple[str, str, str]:
        slug = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in slug:
            owner, name = slug.split("/", 1)
        else:
            owner, name = "local", self.root.resolve().name
        branch = os.environ.get("GITHUB_REF_NAME") or "HEAD"
        return owner, name, branch

    def repos(self) -> list[Repo]:
        owner, name, branch = self._identity()
        return [
            Repo(
                name=name,
                owner=owner,
                default_branch=branch,
                visibility="unknown",
            )
        ]

    def file(self, repo: Repo, path: str) -> str | None:
        try:
            return (self.root / path).read_text()
        except OSError:
            return None

    def list_paths(self, repo: Repo) -> list[str]:
        tracked = self._git_tracked()
        return tracked if tracked is not None else self._walk_files()

    def _git_tracked(self) -> list[str] | None:
        """Tracked file paths via git — mirrors the GitHub tree (honours .gitignore)."""
        try:
            result = proc.run(["git", "-C", str(self.root), "ls-files", "-z"])
        except proc.ToolNotFoundError:
            return None
        if result.returncode != 0:
            return None
        return sorted(path for path in result.stdout.split("\0") if path)

    def _walk_files(self) -> list[str]:
        skip = {"node_modules", ".git", ".venv", "dist", ".output", "__pycache__"}
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [name for name in dirnames if name not in skip]
            base = Path(dirpath)
            out.extend((base / name).relative_to(self.root).as_posix() for name in filenames)
        return sorted(out)

    def write_file(self, repo: Repo, path: str, content: str) -> None:
        (self.root / path).write_text(content)

    def workflows(self, repo: Repo) -> dict[str, str]:
        workflow_dir = self.root / ".github" / "workflows"
        if not workflow_dir.is_dir():
            return {}
        out: dict[str, str] = {}
        for entry in sorted(workflow_dir.iterdir()):
            if entry.is_file() and entry.suffix in (".yml", ".yaml"):
                try:
                    out[entry.name] = entry.read_text()
                except OSError:
                    continue
        return out

    def branch_rules(self, repo: Repo) -> list[dict[str, Any]]:
        raise ControlPlaneUnavailable("branch rules are not readable from a checkout")

    def repo_secrets(self, repo: Repo) -> set[str]:
        raise ControlPlaneUnavailable("secret provisioning is not readable from a checkout")

    def org_secrets(self) -> dict[str, str]:
        raise ControlPlaneUnavailable("org secrets are not readable from a checkout")

    def org_secret_selected_repos(self, name: str) -> set[str]:
        raise ControlPlaneUnavailable("org secrets are not readable from a checkout")

    def ruleset_active(self, name: str) -> bool:
        raise ControlPlaneUnavailable("org rulesets are not readable from a checkout")
