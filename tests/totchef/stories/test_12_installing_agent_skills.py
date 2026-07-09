(
    """User stories §12 — Installing agent skills. One test per §12 criterion on the """
    """real chef in-process; system boundaries (bash, home) are faked."""
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from act_fixtures import Totchef
    from arrange_fixtures import FakeHttp, FakeSkillsRepo, FakeSystem, FakeTerminal, RecipeBuilder
    from totchef.recipe_types import RecipeValue


def test_12_1_1_skills_installs_each_declared_repo_via_the_skills_cli(
    zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef
) -> None:
    """`[skills] repos = [...]` installs each repo globally for Claude Code via `bunx skills add`."""
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))

    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "installed")
    terminal.expect_ran("bunx skills add zyplux/zyp-skills -g --agent claude-code universal --skill '*' -y")


def test_12_1_2_skills_requires_bun_and_bunx_and_fails_hard_pointing_at_url_bun(
    recipe: RecipeBuilder, totchef: Totchef
) -> None:
    """If bun or bunx is missing the run fails hard, telling the operator the [url] bun install must run first."""
    recipe.declares("skills", repos=["zyplux/zyp-skills"])

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("[url.bun]")


def test_12_1_3_each_skill_gets_its_own_report_row_with_version_and_content_id(
    zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """One report row per skill, valued by the skill's declared version — SKILL.md """
        """frontmatter first, then package.json, then pyproject.toml — plus a short #hash """
        """content id, per skill from the very first install."""
    )
    zyp_skills.delivers(
        ("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"),
        ("peek", "ffff6666aaaa7777bbbb8888cccc9999dddd0000"),
        ("h2md", "dddd4444eeee5555ffff6666aaaa7777bbbb8888"),
        ("last30days", "eeee5555ffff6666aaaa7777bbbb8888cccc9999"),
        ("cirq", "bbbb8888cccc9999dddd0000eeee1111ffff2222"),
        files={
            # a decoy `version:` continuation line inside a plain multi-line description
            "totchef": {
                "SKILL.md": "---\nname: totchef\ndescription:\n  Handles React\n  version: 19 upgrades too\n---\n"
            },
            # single-quoted under metadata, as zyp-skills and vercel-labs/agent-skills write it;
            # package.json's version is outranked by SKILL.md's own
            "peek": {
                "SKILL.md": "---\nname: peek\nmetadata:\n  kind: cli\n  version: '0.7.1'\n---\n",
                "package.json": '{"version": "1.2.0"}',
            },
            "h2md": {"pyproject.toml": '[project]\nname = "h2md"\nversion = "0.3.0"\n'},
            # top-level, as last30days-skill writes it
            "last30days": {"SKILL.md": '---\nname: last30days\nversion: "3.8.3"\nauthor: mvanhorn\n---\n'},
            # flow-style mapping, as scientific-agent-skills writes it
            "cirq": {
                "SKILL.md": '---\nname: cirq\nmetadata: {"version": "1.0", "skill-author": "K-Dense Inc."}\n---\n'
            },
        },
    )

    report = totchef.up()

    assert (
        "skills.zyplux/zyp-skills/totchef,(none),#aaaa1111,—,installed" in report.full_table
    )  # no manifest states a version; the decoy stays a decoy
    assert "skills.zyplux/zyp-skills/peek,(none),0.7.1 #ffff6666,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/h2md,(none),0.3.0 #dddd4444,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/last30days,(none),3.8.3 #eeee5555,—,installed" in report.full_table
    assert "skills.zyplux/zyp-skills/cirq,(none),1.0 #bbbb8888,—,installed" in report.full_table


def test_12_1_4_an_installed_skill_reports_unchanged_when_only_its_timestamp_moved(
    zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef
) -> None:
    (
        """The CLI rewrites every skill's updatedAt on each add; a skill whose folder """
        """hash held still reports unchanged, even though the repo was re-synced."""
    )
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")

    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"), synced_at="2026-01-02T00:00:00Z")
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    sync_count = 2  # re-synced on both `up()` runs, despite the second reporting unchanged
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count


def test_12_1_5_an_installed_skill_reports_upgraded_when_its_content_hash_changed(
    zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """When a skill's skillFolderHash moves (its folder's content actually changed """
        """upstream), its row reports upgraded."""
    )
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))
    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "installed")

    zyp_skills.delivers(("totchef", "bbbb2222cccc3333dddd4444eeee5555ffff6666"), synced_at="2026-01-02T00:00:00Z")
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "upgraded")


def test_12_1_6_the_run_log_breaks_down_which_skills_were_new_updated_or_unchanged(
    zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """Each repo's sync logs which of its skills were newly added, which had a """
        """changed content hash, and which were untouched."""
    )
    zyp_skills.delivers(
        ("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"),
        ("peek", "ffff6666aaaa7777bbbb8888cccc9999dddd0000"),
    )
    totchef.up()

    zyp_skills.delivers(
        ("totchef", "bbbb2222cccc3333dddd4444eeee5555ffff6666"),  # hash moved -> updated
        ("peek", "ffff6666aaaa7777bbbb8888cccc9999dddd0000"),  # hash held -> unchanged
        ("mermaid", "cccc3333dddd4444eeee5555ffff6666aaaa7777"),  # new key -> new
        synced_at="2026-01-02T00:00:00Z",
    )
    report = totchef.up()

    report.assert_logged("new: mermaid")
    report.assert_logged("updated: totchef")
    report.assert_logged("unchanged: peek")


def test_12_1_7_a_failed_repo_reports_hard_naming_the_failed_repo(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem
) -> None:
    """If `skills add` fails for a repo, the run reports a hard failure naming it."""
    recipe.declares("skills", repos=["realSergiy/does-not-exist"])
    system.has("bunx", "bun")
    terminal.arrange("skills add realSergiy/does-not-exist", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("realSergiy/does-not-exist")


def test_12_1_8_multiple_repos_install_concurrently(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem
) -> None:
    """Multiple declared repos install concurrently, each via its own `skills add` invocation."""
    repos: list[RecipeValue] = ["zyplux/zyp-skills", "vercel-labs/agent-skills"]
    recipe.declares("skills", repos=repos)
    system.has("bunx", "bun")
    terminal.expect_concurrent(*(f"skills add {repo}" for repo in repos), parties=len(repos))

    report = totchef.up()

    report.assert_succeeded()
    assert terminal.max_concurrent_commands == len(repos)


def test_12_1_9_a_cli_kind_skill_binary_is_chmod_and_linked_onto_path(
    zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef, home: Path
) -> None:
    (
        """A cli-kind skill's package.json `bin` script is chmod'd executable and """
        """`bun link`ed from its own directory, so it resolves on PATH — on every sync, """
        """even a converged one that skipped the CLI."""
    )
    zyp_skills.delivers(
        ("peek", "ffff6666aaaa7777bbbb8888cccc9999dddd0000"),
        files={"peek": {"package.json": '{"bin": "peek.py"}', "peek.py": "#!/usr/bin/env python3\n"}},
    )
    terminal.arrange("bun link")
    zyp_skills.upstream_matches()

    skill_dir = home / ".agents" / "skills" / "peek"

    totchef.up().assert_succeeded()  # installed; the binary is chmod'd and linked alongside
    terminal.expect_ran("bun link")
    assert terminal.cwd_for("bun link") == skill_dir
    assert (
        skill_dir / "peek.py"
    ).stat().st_mode & 0o111  # git doesn't preserve the executable bit; the cook restores it

    (skill_dir / "peek.py").chmod(0o644)  # bit dropped out of band
    totchef.up().assert_succeeded()  # converged: upstream matches, so no reinstall — yet the link is restored
    assert terminal.count("skills add zyplux/zyp-skills") == 1
    assert (skill_dir / "peek.py").stat().st_mode & 0o111


def test_12_1_10_a_plan_shows_one_repo_row_before_install_and_per_skill_rows_after(
    zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """A never-installed repo's skills are unknowable without the network, so a plan """
        """shows one `<repo>` row; once installed, a plan shows one row per skill."""
    )
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))

    totchef.plan().assert_shows("skills.zyplux/zyp-skills", "would install")

    totchef.up()

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "would sync")


def test_12_1_11_an_up_run_skips_the_cli_when_upstream_content_matches(
    installed_totchef_skill: Path, zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef
) -> None:
    (
        """A repo whose skills' upstream folder SHAs all match the lockfile has nothing """
        """to do — `skills add` is not invoked, its skills report unchanged."""
    )
    del installed_totchef_skill
    zyp_skills.upstream_matches()

    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    assert terminal.count("skills add zyplux/zyp-skills") == 1  # the second run never reached the CLI


def test_12_1_12_a_plan_shows_up_to_date_when_upstream_matches(
    installed_totchef_skill: Path, zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    """With upstream reachable and a skill's folder SHA matching the lockfile, a plan shows that skill as up-to-date."""
    del installed_totchef_skill
    zyp_skills.upstream_matches()

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "up-to-date")


def test_12_1_13_a_plan_shows_would_upgrade_when_upstream_content_changed(
    installed_totchef_skill: Path, zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """When a skill's upstream folder SHA differs from the lockfile, a plan shows """
        """would upgrade with the upstream short content id in the latest column."""
    )
    del installed_totchef_skill
    zyp_skills.upstream_holds(("totchef", "bbbb2222cccc3333dddd4444eeee5555ffff6666"))

    report = totchef.plan()

    assert "skills.zyplux/zyp-skills/totchef,#aaaa1111,#aaaa1111,#bbbb2222,would upgrade" in report.full_table


def test_12_1_14_when_github_is_unreachable_every_repo_re_syncs(
    zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef, http: FakeHttp
) -> None:
    (
        """The upstream check is best-effort and tokenless; when the trees call fails, """
        """the cook falls back to refresh-every-run."""
    )
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))
    totchef.up()

    report = totchef.up()  # no http arranged: the trees call fails, as if offline

    report.assert_succeeded()
    http.expect_fetched("api.github.com/repos/zyplux/zyp-skills/git/trees/HEAD")  # the check was attempted...
    sync_count = 2  # ...and its failure fell back to re-syncing on both `up()` runs
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count


def test_12_1_15_a_drifted_agent_entry_re_adds_to_restore_the_store_symlink(
    installed_totchef_skill: Path, zyp_skills: FakeSkillsRepo, terminal: FakeTerminal, totchef: Totchef
) -> None:
    (
        """An agent entry that isn't the symlink into the canonical store (a real-dir """
        """copy from an older install) is drift: the plan shows would sync despite """
        """upstream matching, and up re-adds the repo so the CLI replaces the copy """
        """with the symlink."""
    )
    zyp_skills.upstream_matches()
    agent_entry = installed_totchef_skill
    agent_entry.unlink()
    agent_entry.mkdir()
    (agent_entry / "SKILL.md").write_text(
        "---\nname: totchef\n---\n"
    )  # a real-dir copy, as an old copy-mode install left it

    totchef.plan().assert_shows("skills.zyplux/zyp-skills/totchef", "would sync")

    totchef.up().assert_shows("skills.zyplux/zyp-skills/totchef", "unchanged")
    sync_count = 2  # re-added to repair the drift, on top of the initial install
    assert terminal.count("skills add zyplux/zyp-skills") == sync_count
    assert agent_entry.is_symlink()  # the copy is gone; the entry links into the store again


def test_12_1_16_a_re_add_reports_a_newly_landed_skill_as_its_own_installed_row(
    zyp_skills: FakeSkillsRepo, totchef: Totchef
) -> None:
    (
        """A skill that first appears during a re-add of an already-installed repo gets """
        """its own report row, not just the sync-log mention."""
    )
    zyp_skills.delivers(("totchef", "aaaa1111bbbb2222cccc3333dddd4444eeee5555"))
    totchef.up()

    zyp_skills.delivers(
        ("totchef", "bbbb2222cccc3333dddd4444eeee5555ffff6666"),
        ("mermaid", "cccc3333dddd4444eeee5555ffff6666aaaa7777"),
        synced_at="2026-01-02T00:00:00Z",
    )
    report = totchef.up()

    report.assert_shows("skills.zyplux/zyp-skills/totchef", "upgraded")
    report.assert_shows("skills.zyplux/zyp-skills/mermaid", "installed")
