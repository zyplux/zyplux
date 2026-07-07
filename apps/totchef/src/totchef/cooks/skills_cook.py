"""VersionedCook for [skills] — Claude Code skills fetched from GitHub repos via the `skills` CLI (skills.sh), run through `bunx`. Every add targets `--agent claude-code universal`: two distinct agent dirs keep the CLI in symlink mode (a single-agent add silently switches to copy mode and strands the store), so each skill's files live once in the canonical ~/.agents/skills store — the source of truth any agent can share — and ~/.claude/skills/<skill> symlinks into it. An agent entry that isn't that symlink (say a real-dir copy from an old copy-mode install) is drift: its upstream state reports unknown, which re-adds the repo and lets the CLI replace the copy with the symlink. The CLI's own ~/.agents/.skill-lock.json holds one entry per skill, whose `skillFolderHash` (the GitHub tree SHA of the skill's folder) is the only content-change signal — the lockfile's `updatedAt` is rewritten on every `add`, changed or not. `find_latest` asks upstream with one unauthenticated GitHub trees call per installed repo (the same endpoint the CLI's own `update` uses, minus its token fallback), so a repo whose skills all match upstream skips `skills add` entirely; an unreachable GitHub degrades to refresh-every-run. The report is one row per installed skill, keyed `<repo>/<skill>`, valued by the skill's declared version (SKILL.md frontmatter, then package.json, then pyproject.toml) plus a short `#hash` content id; a never-installed repo's skills are unknowable before its first `add`, so it plans as a single repo row that `list_reportable` splits into per-skill rows once the install lands. A "cli"-kind skill (e.g. peek) ships its own package.json `bin`; the skills CLI installs its files but never chmods or links that binary onto PATH, so this cook does — chmod +x plus `bun link` from the skill's own directory, on every sync (even a converged one), best-effort and idempotent like bun_cook's node shim. Runs as the invoking user; depends on [url] (bun)."""

import json
import os
import subprocess
import tomllib

import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from totchef import shell
from totchef.cook_base import EntrySpec, SyncOutcome, VersionedCook
from totchef.harness import fetch_latest_concurrent, fetch_url, find_binary

AGENTS = ("claude-code", "universal")
GITHUB_TREES_URL = "https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"


class SkillsConfig(EntrySpec):
    repos: list[str] = []


def lockfile_path() -> Path:
    """The `skills` CLI's own global lockfile; resolved at call time so it follows become_user's $HOME drop in a forked child."""
    return Path.home() / ".agents" / ".skill-lock.json"


def canonical_skills_dir() -> Path:
    """The CLI's canonical store, where a symlink-mode add puts each skill's files — the source of truth for version reads and CLI-binary linking; resolved at call time, same reasoning as lockfile_path."""
    return Path.home() / ".agents" / "skills"


def agent_skills_dir() -> Path:
    """Claude Code's own skills dir, resolved the way the CLI does (${CLAUDE_CONFIG_DIR:-~/.claude}/skills); a symlink-mode add fills it with symlinks into the canonical store."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return (Path(config_dir) if config_dir else Path.home() / ".claude") / "skills"


def is_agent_linked(name: str) -> bool:
    """Whether a skill's agent entry is the symlink into the canonical store that a symlink-mode add creates — anything else (a real-dir copy from an old copy-mode install, a dangling or foreign link) is drift, repaired by re-adding the repo."""
    agent_entry = agent_skills_dir() / name
    return agent_entry.is_symlink() and agent_entry.exists() and agent_entry.resolve() == (canonical_skills_dir() / name).resolve()


def lockfile_skills() -> dict[str, dict]:
    try:
        payload = json.loads(lockfile_path().read_text())
    except OSError, json.JSONDecodeError:
        return {}
    return payload.get("skills", {})


def read_skill_md_version(skill_dir: Path) -> str | None:
    """The version declared in SKILL.md's YAML frontmatter, wherever the wild puts it: nested under `metadata:` (zyp-skills, vercel-labs — including flow-style `metadata: {"version": ...}`) or at the top level (last30days). A real YAML parse, because a line match false-positives on `version:` continuation lines inside plain multi-line descriptions."""
    skill_md = skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    try:
        frontmatter = yaml.safe_load(text[3:].split("\n---", 1)[0])
    except yaml.YAMLError:
        return None
    if not isinstance(frontmatter, dict):
        return None
    metadata = frontmatter.get("metadata")
    version = frontmatter.get("version") or (metadata.get("version") if isinstance(metadata, dict) else None)
    return str(version) if version is not None else None


def read_package_json_version(skill_dir: Path) -> str | None:
    try:
        return json.loads((skill_dir / "package.json").read_text()).get("version")
    except OSError, json.JSONDecodeError:
        return None


def read_pyproject_version(skill_dir: Path) -> str | None:
    try:
        return tomllib.loads((skill_dir / "pyproject.toml").read_text()).get("project", {}).get("version")
    except OSError, tomllib.TOMLDecodeError:
        return None


def read_skill_version(name: str) -> str | None:
    """A skill's declared version, from the first manifest that states one: SKILL.md frontmatter, then package.json, then pyproject.toml."""
    skill_dir = canonical_skills_dir() / name
    return read_skill_md_version(skill_dir) or read_package_json_version(skill_dir) or read_pyproject_version(skill_dir)


def skill_state(name: str, info: dict) -> str:
    """One skill's report value: its declared version when it states one, plus a short content id from the lockfile's folder hash. The hash — not `updatedAt`, which the CLI rewrites on every `add` — is what actually moves when the skill's content changed."""
    folder_hash = info.get("skillFolderHash")
    content_id = f"#{folder_hash[:8]}" if folder_hash else info.get("updatedAt", "?")
    version = read_skill_version(name)
    return f"{version} {content_id}" if version else content_id


def read_skill_states() -> dict[str, str]:
    """Every installed skill keyed `<repo>/<skill>`, straight from the lockfile the `skills` CLI already maintains."""
    return {f"{info['source']}/{name}": skill_state(name, info) for name, info in lockfile_skills().items()}


def skills_for_source(skills: dict[str, dict], source: str) -> dict[str, str]:
    return {name: skill_state(name, info) for name, info in skills.items() if info.get("source") == source}


def repo_ref(skills: dict[str, dict], repo: str) -> str:
    """The git ref a repo's skills were installed from (the lockfile records one when the source pinned it), HEAD — the default branch — otherwise."""
    return next((info["ref"] for info in skills.values() if info.get("source") == repo and info.get("ref")), "HEAD")


def find_folder_sha(tree: dict, skill_path: str) -> str | None:
    """The tree SHA of one skill's folder inside a fetched repo tree — mirrors the skills CLI's getSkillFolderHashFromTree, including the root-level-skill case where the repo's own SHA is the folder hash."""
    folder = skill_path.replace("\\", "/")
    if folder.lower().endswith("skill.md"):
        folder = folder[: -len("skill.md")]
    folder = folder.rstrip("/")
    if not folder:
        return tree.get("sha")
    return next((entry.get("sha") for entry in tree.get("tree", []) if entry.get("type") == "tree" and entry.get("path") == folder), None)


def fetch_repo_trees(repos: list[str], skills: dict[str, dict]) -> dict[str, dict | None]:
    """One unauthenticated GitHub trees call per repo, concurrently — the same endpoint the skills CLI's own `update` uses. Deliberately no token fallback: a rate-limited or unreachable check degrades to 'latest unknown' (refresh-every-run), it never spawns a credential prompt."""

    def fetch_one(repo: str) -> str:
        return fetch_url(GITHUB_TREES_URL.format(repo=repo, ref=repo_ref(skills, repo))).decode()

    trees: dict[str, dict | None] = {}
    for repo, payload in fetch_latest_concurrent(repos, fetch_one).items():
        try:
            trees[repo] = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            trees[repo] = None
    return trees


def upstream_skill_state(name: str, info: dict, tree: dict) -> str | None:
    """What one skill's report value would read after a sync, judged from upstream: the installed state when the upstream folder SHA matches the lockfile (nothing to do), the new short content id when it moved, unknown when the lock entry or tree can't say."""
    locked_hash, skill_path = info.get("skillFolderHash"), info.get("skillPath")
    if not locked_hash or not skill_path:
        return None
    upstream_sha = find_folder_sha(tree, skill_path)
    if not upstream_sha:
        return None
    return skill_state(name, info) if upstream_sha == locked_hash else f"#{upstream_sha[:8]}"


def describe_skill_changes(before: dict[str, str], after: dict[str, str]) -> str:
    """A per-skill new/updated/unchanged breakdown for one repo's sync, read from the lockfile snapshot taken before and after `skills add` ran."""
    new = sorted(set(after) - set(before))
    updated = sorted(name for name in after.keys() & before.keys() if after[name] != before[name])
    unchanged = sorted(name for name in after.keys() & before.keys() if after[name] == before[name])
    parts = [f"{label}: {', '.join(names)}" for label, names in (("new", new), ("updated", updated), ("unchanged", unchanged)) if names]
    return "; ".join(parts) if parts else "no skills found"


def bin_paths(package_json: Path) -> list[str]:
    """The script path(s) a skill's package.json declares as `bin` — a dict of {name: path} for one-or-many named binaries, or a bare string for a single binary named after the package itself."""
    try:
        bin_field = json.loads(package_json.read_text()).get("bin")
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"could not read {package_json}: {exc}")
        return []
    if isinstance(bin_field, dict):
        return list(bin_field.values())
    return [bin_field] if bin_field else []


def link_cli_binary(bun: Path, name: str) -> None:
    """A "cli"-kind skill ships its own package.json `bin`; the skills CLI installs the files but never chmods or links the binary onto PATH. Mirror zyp-skills' skillman.py: chmod the script executable (git doesn't preserve the bit) and `bun link` from within the skill's canonical store directory. Best-effort and idempotent, like bun_cook's node shim — runs on every sync, so a converged re-run restores the link if it was removed."""
    skill_dir = canonical_skills_dir() / name
    package_json = skill_dir / "package.json"
    if not package_json.exists():
        return
    scripts = bin_paths(package_json)
    if not scripts:
        return
    for bin_path in scripts:
        script = skill_dir / bin_path
        if script.exists():
            script.chmod(script.stat().st_mode | 0o111)
    try:
        shell.stream([str(bun), "link"], note=f"Linking {name} CLI binary", cwd=skill_dir)
    except subprocess.CalledProcessError as exc:
        logger.warning(f"{name}: could not link CLI binary: {exc}")


class SkillsCook(VersionedCook):
    entry_model = SkillsConfig

    def __init__(self, section: dict) -> None:
        super().__init__(section)
        config = SkillsConfig.model_validate(section)
        self.repos = config.repos
        self.hooks = (config.pre_hook, config.post_hook)

    def list_requested(self) -> list[str]:
        """Per-skill keys for every repo the lockfile already knows, the bare repo as a placeholder otherwise — its skills are unknowable before the first `skills add`."""
        skills = lockfile_skills()
        requested: list[str] = []
        for repo in self.repos:
            skill_keys = sorted(f"{repo}/{name}" for name, info in skills.items() if info.get("source") == repo)
            requested += skill_keys or [repo]
        return requested

    def get_hooks(self) -> tuple[str | None, str | None]:
        return self.hooks

    def list_installed(self) -> dict[str, str]:
        return read_skill_states()

    def list_reportable(self, requested: list[str], installed_after: dict[str, str]) -> list[str]:
        """Row keys per declared repo: every skill installed after the sync — including one a re-add newly landed, which no requested key could name up front — plus any requested key nothing landed for (a fresh-repo placeholder whose add failed, a skill that vanished), so failures keep their rows."""
        reportable: list[str] = []
        for repo in self.repos:
            landed = sorted(key for key in installed_after if key.startswith(f"{repo}/"))
            lost = [key for key in requested if key.startswith(f"{repo}/") and key not in installed_after]
            reportable += (landed + lost) or [repo]
        return reportable

    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        """Upstream state per requested key, from one trees call per already-installed repo. A fresh-repo placeholder stays unknown (its skills are unknowable before the first add), as does every key of an unreachable repo and every drifted skill (its agent entry isn't the store symlink) — unknown falls back to refresh-every-run."""
        skills = lockfile_skills()
        installed_repos = [repo for repo in self.repos if any(info.get("source") == repo for info in skills.values())]
        trees = fetch_repo_trees(installed_repos, skills)
        latest: dict[str, str | None] = {}
        for key in names:
            repo = self._repo_of(key)
            tree = trees.get(repo)
            if key == repo or tree is None:
                latest[key] = None
                continue
            name = key.removeprefix(f"{repo}/")
            latest[key] = upstream_skill_state(name, skills[name], tree) if is_agent_linked(name) else None
        return latest

    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        bunx = find_binary("bunx")
        bun = find_binary("bun")
        if not bunx or not bun:
            return SyncOutcome("hard_fail", "bun/bunx not found — the [url.bun] section must run before [skills].")

        repos = list(dict.fromkeys(self._repo_of(target) for target in to_install + to_upgrade))
        failures: list[str] = []
        changes: dict[str, str] = {}
        if repos:
            logger.info(f"Installing/refreshing skills from {len(repos)} repo(s): " + ", ".join(repos))
            tag_width = max(len(repo) for repo in repos)
            with ThreadPoolExecutor(max_workers=len(repos)) as pool:
                pending = {pool.submit(self._add_one, bunx, repo, tag_width): repo for repo in repos}
                for future in as_completed(pending):
                    repo = pending[future]
                    try:
                        changes[repo] = future.result()
                    except Exception as exc:
                        failures.append(repo)
                        logger.error(f"{repo} failed: {exc}")

        for name, info in lockfile_skills().items():
            if info.get("source") in self.repos:
                link_cli_binary(bun, name)

        if failures:
            return SyncOutcome("hard_fail", f"{len(failures)} skill repo(s) failed: " + ", ".join(failures))
        return SyncOutcome("ok", "; ".join(f"{repo} ({change})" for repo, change in changes.items()))

    def _repo_of(self, target: str) -> str:
        """The declared repo a diff key belongs to — itself for a fresh-repo placeholder, its `<repo>/` prefix for a per-skill key."""
        return next(repo for repo in self.repos if target == repo or target.startswith(f"{repo}/"))

    @staticmethod
    def _add_one(bunx: Path, repo: str, tag_width: int) -> str:
        before = skills_for_source(lockfile_skills(), repo)
        shell.stream(
            [str(bunx), "skills", "add", repo, "-g", "--agent", *AGENTS, "--skill", "*", "-y"],
            f"[{repo:>{tag_width}}]",
            note="Installing skills",
        )
        return describe_skill_changes(before, skills_for_source(lockfile_skills(), repo))
