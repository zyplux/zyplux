"""User stories §12 — Installing agent skills. One test per §12 criterion on the real chef in-process; system boundaries (bash, home) are faked."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from act_fixtures import Totchef
    from arrange_fixtures import FakeHttp, FakeSystem, FakeTerminal, RecipeBuilder
    from totchef.recipe_types import RecipeValue


def _write_skills(home: Path, *entries: tuple[str, str, str, str]) -> Callable[[], None]:
    (
        """An effect simulating `skills add` writing the skills CLI's own lockfile — `entries` is the full (name, source, folder_hash, updated_at) """
        """state it holds after this call. The real CLI rewrites updatedAt on every add whether or not content changed; only folder_hash tracks """
        """the content."""
    )
    skills = ",".join(
        '"'
        + name
        + '": {"source": "'
        + source
        + '", "skillFolderHash": "'
        + folder_hash
        + '", "updatedAt": "'
        + updated_at
        + '", "skillPath": "skills/'
        + name
        + '/SKILL.md"}'
        for name, source, folder_hash, updated_at in entries
    )

    def write() -> None:
        lock_dir = home / ".agents"
        lock_dir.mkdir(parents=True, exist_ok=True)
        (lock_dir / ".skill-lock.json").write_text('{"version": 3, "skills": {' + skills + "}}")

    return write


def _github_tree(*skill_folders: tuple[str, str]) -> str:
    (
        """The GitHub trees API response for a repo — one (skill_name, folder_sha) tree entry per skill, at the `skills/<name>` path the lockfile's """
        """skillPath points into."""
    )
    entries = ",".join('{"path": "skills/' + name + '", "type": "tree", "sha": "' + sha + '"}' for name, sha in skill_folders)
    return '{"sha": "root0000root0000root0000root0000root0000", "tree": [' + entries + "]}"


def _run(*effects: Callable[[], None]) -> Callable[[], None]:
    """Combine several effects into the single callback `terminal.arrange` takes, run in order."""

    def run() -> None:
        for effect in effects:
            effect()

    return run


def _drop_skill_files(home: Path, name: str, **files: str) -> Callable[[], None]:
    (
        """An effect simulating a symlink-mode `skills add` writing a skill's own files: they land in the canonical store `~/.agents/skills/<name>`, """
        """and `~/.claude/skills/<name>` becomes a symlink to it (replacing whatever sat there, as the CLI's createSymlink does). Filenames given """
        """with `_` for `.` (skill_md -> SKILL.md, package_json -> package.json, pyproject_toml -> pyproject.toml, any other name verbatim); every """
        """file arrives non-executable, since git doesn't preserve that bit."""
    )
    manifest_names = {"skill_md": "SKILL.md", "package_json": "package.json", "pyproject_toml": "pyproject.toml"}

    def write() -> None:
        skill_dir = home / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        for key, content in files.items():
            dropped = skill_dir / manifest_names.get(key, key)
            dropped.write_text(content)
            dropped.chmod(0o644)
        agent_entry = home / ".claude" / "skills" / name
        agent_entry.parent.mkdir(parents=True, exist_ok=True)
        if agent_entry.is_symlink():
            agent_entry.unlink()
        elif agent_entry.is_dir():
            for stale in sorted(agent_entry.rglob("*"), reverse=True):
                stale.rmdir() if stale.is_dir() else stale.unlink()
            agent_entry.rmdir()
        agent_entry.symlink_to(skill_dir)

    return write


def test_12_1_1_skills_installs_each_declared_repo_via_the_skills_cli(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """`[skills] repos = [...]` installs each repo globally for Claude Code via `bunx skills add`."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )

    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "installed")
    terminal.expect_ran("bunx skills add zyplux/zyp-skills -g --agent claude-code universal --skill '*' -y")


def test_12_1_2_skills_requires_bun_and_bunx_and_fails_hard_pointing_at_url_bun(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """If bun or bunx is missing the run fails hard, telling the operator the [url] bun install must run first."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("[url.bun]")


def test_12_1_3_each_skill_gets_its_own_report_row_with_version_and_content_id(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    (
        """One report row per skill, valued by the skill's declared version — SKILL.md frontmatter first, then package.json, then pyproject.toml """
        """— plus a short #hash content id, per skill from the very first install."""
    )
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(
        home,
        ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"),
        ("peek", "zyplux/zyp-skills", "ffff6666aaaa7777bbbb8888cccc9999dddd0000", "2026-01-01T00:00:00Z"),
        ("h2md", "zyplux/zyp-skills", "dddd4444eeee5555ffff6666aaaa7777bbbb8888", "2026-01-01T00:00:00Z"),
        ("last30days", "zyplux/zyp-skills", "eeee5555ffff6666aaaa7777bbbb8888cccc9999", "2026-01-01T00:00:00Z"),
        ("cirq", "zyplux/zyp-skills", "bbbb8888cccc9999dddd0000eeee1111ffff2222", "2026-01-01T00:00:00Z"),
    )
    # a decoy `version:` continuation line inside a plain multi-line description
    totchef_skill = _drop_skill_files(
        home,
        "totchef",
        skill_md="---\nname: totchef\ndescription:\n  Handles React\n  version: 19 upgrades too\n---\n",
    )
    # single-quoted under metadata, as zyp-skills and vercel-labs/agent-skills write it
    peek = _drop_skill_files(
        home,
        "peek",
        skill_md="---\nname: peek\nmetadata:\n  kind: cli\n  version: '0.7.1'\n---\n",
        package_json='{"version": "1.2.0"}',  # outranked by SKILL.md's own version
    )
    h2md = _drop_skill_files(home, "h2md", pyproject_toml='[project]\nname = "h2md"\nversion = "0.3.0"\n')
    last30days = _drop_skill_files(
        home, "last30days", skill_md='---\nname: last30days\nversion: "3.8.3"\nauthor: mvanhorn\n---\n'
    )  # top-level, as last30days-skill writes it
    cirq = _drop_skill_files(
        home, "cirq", skill_md='---\nname: cirq\nmetadata: {"version": "1.0", "skill-author": "K-Dense Inc."}\n---\n'
    )  # flow-style mapping, as scientific-agent-skills writes it
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, totchef_skill, peek, h2md, last30days, cirq))

    report = totchef.up()

    assert "skills.zyplux/zyp-skills/totchef,(none),#aaaa1111,—,installed" in report.full_table  # no manifest states a version; the decoy stays a decoy
    assert "skills.zyplux/zyp-skills/peek,(none),0.7.1 #ffff6666,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/h2md,(none),0.3.0 #dddd4444,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/last30days,(none),3.8.3 #eeee5555,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/cirq,(none),1.0 #bbbb8888,—,installed" in report.full_table


def test_12_1_4_an_installed_skill_reports_unchanged_when_only_its_timestamp_moved(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """The CLI rewrites every skill's updatedAt on each add; a skill whose folder hash held still reports unchanged, even though the repo was re-synced."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")

    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-02T00:00:00Z")),
    )
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    sync_count = 2  # re-synced on both `up()` runs, despite the second reporting unchanged
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count


def test_12_1_5_an_installed_skill_reports_upgraded_when_its_content_hash_changed(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """When a skill's skillFolderHash moves (its folder's content actually changed upstream), its row reports upgraded."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")

    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "bbbb2222cccc3333dddd4444eeee5555ffff6666", "2026-01-02T00:00:00Z")),
    )
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "upgraded")


def test_12_1_6_the_run_log_breaks_down_which_skills_were_new_updated_or_unchanged(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """Each repo's sync logs which of its skills were newly added, which had a changed content hash, and which were untouched."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(
            home,
            ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"),
            ("peek", "zyplux/zyp-skills", "ffff6666aaaa7777bbbb8888cccc9999dddd0000", "2026-01-01T00:00:00Z"),
        ),
    )
    totchef.up()

    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(
            home,
            ("totchef", "zyplux/zyp-skills", "bbbb2222cccc3333dddd4444eeee5555ffff6666", "2026-01-02T00:00:00Z"),  # hash moved -> updated
            ("peek", "zyplux/zyp-skills", "ffff6666aaaa7777bbbb8888cccc9999dddd0000", "2026-01-02T00:00:00Z"),  # hash held -> unchanged
            ("mermaid", "zyplux/zyp-skills", "cccc3333dddd4444eeee5555ffff6666aaaa7777", "2026-01-02T00:00:00Z"),  # new key -> new
        ),
    )
    report = totchef.up()

    report.assert_logged("new: mermaid")
    report.assert_logged("updated: totchef")
    report.assert_logged("unchanged: peek")


def test_12_1_7_a_failed_repo_reports_hard_naming_the_failed_repo(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem) -> None:
    """If `skills add` fails for a repo, the run reports a hard failure naming it."""
    recipe.declares("skills", repos=["realSergiy/does-not-exist"])
    system.has("bunx", "bun")
    terminal.arrange("skills add realSergiy/does-not-exist", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("realSergiy/does-not-exist")


def test_12_1_8_multiple_repos_install_concurrently(recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem) -> None:
    """Multiple declared repos install concurrently, each via its own `skills add` invocation."""
    repos: list[RecipeValue] = ["zyplux/zyp-skills", "vercel-labs/agent-skills"]
    recipe.declares("skills", repos=repos)
    system.has("bunx", "bun")
    terminal.expect_concurrent(*(f"skills add {repo}" for repo in repos), parties=len(repos))

    report = totchef.up()

    report.assert_succeeded()
    assert terminal.max_concurrent_commands == len(repos)


def test_12_1_9_a_cli_kind_skill_binary_is_chmod_and_linked_onto_path(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    (
        """A cli-kind skill's package.json `bin` script is chmod'd executable and `bun link`ed from its own directory, so it resolves on PATH """
        """— on every sync, even a converged one that skipped the CLI."""
    )
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(home, ("peek", "zyplux/zyp-skills", "ffff6666aaaa7777bbbb8888cccc9999dddd0000", "2026-01-01T00:00:00Z"))
    files = _drop_skill_files(home, "peek", package_json='{"bin": "peek.py"}', **{"peek.py": "#!/usr/bin/env python3\n"})
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, files))
    terminal.arrange("bun link")
    http.arrange("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD", _github_tree(("peek", "ffff6666aaaa7777bbbb8888cccc9999dddd0000")))

    skill_dir = home / ".agents" / "skills" / "peek"

    totchef.up().assert_succeeded()  # installed; the binary is chmod'd and linked alongside
    terminal.expect_ran("bun link")
    assert terminal.cwd_for("bun link") == skill_dir
    assert (skill_dir / "peek.py").stat().st_mode & 0o111  # git doesn't preserve the executable bit; the cook restores it

    (skill_dir / "peek.py").chmod(0o644)  # bit dropped out of band
    totchef.up().assert_succeeded()  # converged: upstream matches, so no reinstall — yet the link is restored
    assert terminal.count("skills add zyplux/zyp-skills") == 1
    assert (skill_dir / "peek.py").stat().st_mode & 0o111


def test_12_1_10_a_plan_shows_one_repo_row_before_install_and_per_skill_rows_after(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """A never-installed repo's skills are unknowable without the network, so a plan shows one `<repo>` row; once installed, a plan shows one row per skill."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )

    totchef.plan().assert_shows("skills.zyplux/zyp-skills", "would install")

    totchef.up()

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "would sync")


def test_12_1_11_an_up_run_skips_the_cli_when_upstream_content_matches(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    """A repo whose skills' upstream folder SHAs all match the lockfile has nothing to do — `skills add` is not invoked, its skills report unchanged."""
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"))
    files = _drop_skill_files(home, "totchef", skill_md="---\nname: totchef\n---\n")
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, files))
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")

    http.arrange("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD", _github_tree(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555")))
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    assert terminal.count("skills add zyplux/zyp-skills") == 1  # the second run never reached the CLI


def test_12_1_12_a_plan_shows_up_to_date_when_upstream_matches(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    """With upstream reachable and a skill's folder SHA matching the lockfile, a plan shows that skill as up-to-date."""
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"))
    files = _drop_skill_files(home, "totchef", skill_md="---\nname: totchef\n---\n")
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, files))
    totchef.up()

    http.arrange("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD", _github_tree(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555")))

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "up-to-date")


def test_12_1_13_a_plan_shows_would_upgrade_when_upstream_content_changed(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    """When a skill's upstream folder SHA differs from the lockfile, a plan shows would upgrade with the upstream short content id in the latest column."""
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"))
    files = _drop_skill_files(home, "totchef", skill_md="---\nname: totchef\n---\n")
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, files))
    totchef.up()

    http.arrange("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD", _github_tree(("totchef", "bbbb2222cccc3333dddd4444eeee5555ffff6666")))
    report = totchef.plan()

    assert "skills.zyplux/zyp-skills/totchef,#aaaa1111,#aaaa1111,#bbbb2222,would upgrade" in report.full_table


def test_12_1_14_when_github_is_unreachable_every_repo_re_syncs(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    """The upstream check is best-effort and tokenless; when the trees call fails, the cook falls back to refresh-every-run."""
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )
    totchef.up()

    report = totchef.up()  # no http arranged: the trees call fails, as if offline

    report.assert_succeeded()
    http.expect_fetched("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD")  # the check was attempted...
    sync_count = 2  # ...and its failure fell back to re-syncing on both `up()` runs
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count


def test_12_1_15_a_drifted_agent_entry_re_adds_to_restore_the_store_symlink(
    terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path, http: FakeHttp
) -> None:
    (
        """An agent entry that isn't the symlink into the canonical store (a real-dir copy from an older install) is drift: the plan shows would sync """
        """despite upstream matching, and up re-adds the repo so the CLI replaces the copy with the symlink."""
    )
    recipe = totchef.recipe
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    lockfile = _write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z"))
    files = _drop_skill_files(home, "totchef", skill_md="---\nname: totchef\n---\n")
    terminal.arrange("skills add zyplux/zyp-skills", effect=_run(lockfile, files))
    totchef.up()
    http.arrange("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD", _github_tree(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555")))

    agent_entry = home / ".claude" / "skills" / "totchef"
    agent_entry.unlink()
    agent_entry.mkdir()
    (agent_entry / "SKILL.md").write_text("---\nname: totchef\n---\n")  # a real-dir copy, as an old copy-mode install left it

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "would sync")

    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    sync_count = 2  # re-added to repair the drift, on top of the initial install
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count
    assert agent_entry.is_symlink()  # the copy is gone; the entry links into the store again


def test_12_1_16_a_re_add_reports_a_newly_landed_skill_as_its_own_installed_row(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem, home: Path
) -> None:
    """A skill that first appears during a re-add of an already-installed repo gets its own report row, not just the sync-log mention."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])
    system.has("bunx", "bun")
    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(home, ("totchef", "zyplux/zyp-skills", "aaaa1111bbbb2222cccc3333dddd4444eeee5555", "2026-01-01T00:00:00Z")),
    )
    totchef.up()

    terminal.arrange(
        "skills add zyplux/zyp-skills",
        effect=_write_skills(
            home,
            ("totchef", "zyplux/zyp-skills", "bbbb2222cccc3333dddd4444eeee5555ffff6666", "2026-01-02T00:00:00Z"),
            ("mermaid", "zyplux/zyp-skills", "cccc3333dddd4444eeee5555ffff6666aaaa7777", "2026-01-02T00:00:00Z"),
        ),
    )
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "upgraded")
    report.assert_shows("skills.zyplux/zyp-skills/mermaid", "installed")
