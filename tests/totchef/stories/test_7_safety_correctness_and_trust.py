"""User stories §7 — Safety and trust. One test per §7 criterion; most drive the chef, the escalation story runs `totchef up` via `cli` with exec faked."""

GIT_NEEDS_INSTALL = "git:\n  Installed: (none)\n  Candidate: 1:2.40\n  Version table:\n     1:2.40 500\n        500 http://archive noble/main amd64 Packages\n"


# 7.1 Trust that re-runs only change what drifted


def test_7_1_1_cooks_probe_and_act_only_on_the_difference(recipe, terminal, http, totchef, system, tmp_path):
    """Versioned cooks skip up-to-date packages; state cooks skip resources whose content hash already matches."""
    already = tmp_path / "already.conf"
    already.write_text("A\n")
    recipe.declares("cargo", packages=["ripgrep"])
    recipe.declares("file", "f", path=str(already), content="A\n")
    system.has("cargo", "cargo-binstall")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n    rg\n")

    report = totchef.up()

    report.assert_shows("cargo.ripgrep", "unchanged")
    report.assert_shows("file.f", "unchanged")
    terminal.expect_not_ran("binstall")


def test_7_1_2_post_hooks_fire_only_on_actual_change(recipe, terminal, totchef, tmp_path):
    """post_hooks fire only on actual change, so refreshes don't run on no-op passes."""
    target = tmp_path / "unit.service"
    recipe.declares("file", "unit", path=str(target), content="[Unit]\n", post_hook="systemctl daemon-reload")

    totchef.up().assert_shows("file.unit", "applied")
    terminal.expect_ran("daemon-reload")

    terminal.reset()
    totchef.up().assert_shows("file.unit", "unchanged")
    terminal.expect_not_ran("daemon-reload")


# 7.2 Understand that totchef creates and updates but never prunes


def test_7_2_1_convergence_is_create_update_only_never_prunes(recipe, totchef, tmp_path):
    """Dropping an entry leaves prior artifacts in place; teardown is manual."""
    artifact = tmp_path / "drop-in.conf"
    recipe.declares("file", "drop_in", path=str(artifact), content="X\n")

    totchef.up().assert_shows("file.drop_in", "applied")
    assert artifact.exists()

    del recipe.config["file"]  # operator removes the entry from the recipe
    totchef.up().assert_succeeded()

    assert artifact.exists()  # the artifact is left in place — teardown is manual


# 7.3 Escalate to root only for the apply, and drop privilege otherwise


def test_7_3_1_up_re_execs_under_sudo_pinning_recipe_and_log(cli, monkeypatch, tmp_path):
    """`totchef up` re-execs under sudo, pinning the resolved recipe path and shared log file across the boundary."""
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[bash.step]\napply = "true"\n')
    escalation: dict = {}

    def capture_exec(target, argv):
        escalation.update(target=target, argv=list(argv))
        raise SystemExit(0)  # sudo replaces the process — control never returns

    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root yet
    monkeypatch.setattr("os.execvp", capture_exec)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    cli.run("up", "--recipe", str(recipe_path))

    assert escalation["target"] == "sudo"  # re-execs under sudo
    preserve = next(arg for arg in escalation["argv"] if arg.startswith("--preserve-env="))
    assert "TOTCHEF_RECIPE" in preserve and "LOG" in preserve  # recipe and log file pinned across the boundary
    cli.run("where").assert_prints(str(recipe_path))  # the pinned recipe is what a fresh resolution now finds


def test_7_3_2_forked_child_drops_privilege_for_user_nodes(apply_in_container):
    """A forked child keeps root if needs_root, else drops to the invoking user — user files written as the user, root entries as root. In a container."""
    run = apply_in_container(
        '[file.user_node]\npath = "/home/tester/by-user.txt"\ncontent = "u\\n"\n\n'
        '[file.root_node]\nneeds_root = true\npath = "/home/tester/by-root.txt"\ncontent = "r\\n"\n',
        ["/home/tester/by-user.txt", "/home/tester/by-root.txt"],
    )

    assert run.owners["/home/tester/by-user.txt"] == "tester", run.transcript  # dropped to the user
    assert run.owners["/home/tester/by-root.txt"] == "root", run.transcript  # needs_root kept root


def test_7_3_3_plan_and_lint_never_escalate(recipe, terminal, totchef, cli, monkeypatch, tmp_path):
    """plan and lint never escalate."""
    recipe.declares("apt_pkg", packages=["git"])  # a root-scoped cook
    terminal.arrange("apt-cache policy git", GIT_NEEDS_INSTALL)

    totchef.plan().assert_shows("apt_pkg.git", "would install")
    terminal.expect_not_ran("nala")  # probed, but no privileged transaction

    totchef.lint().assert_valid()  # validates only — no shell, no root
    terminal.expect_not_ran("nala")

    # the real gate: from a non-root euid, neither command re-execs under sudo
    escalations: list = []
    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root — so any escalation would call execvp
    monkeypatch.setattr("os.execvp", lambda *argv: escalations.append(argv))
    monkeypatch.setattr("totchef.cli.run_recipe", lambda config, dry_run: {})  # don't fork real cooks in-process
    monkeypatch.setattr("totchef.cli.start_logging", lambda echo_to_terminal=True: tmp_path / "log")
    monkeypatch.setattr("totchef.cli.drain_logs", lambda: None)
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[apt_pkg]\npackages = ["git"]\n')

    cli.run("plan", "--recipe", str(recipe_path))
    cli.run("lint", "--recipe", str(recipe_path)).assert_prints(": valid")

    assert escalations == []  # neither plan nor lint escalated, though apt_pkg is a root-scoped cook


def test_7_3_4_frozen_binary_re_execs_by_absolute_path_not_argv0_name(cli, monkeypatch, tmp_path):
    """A frozen single-file binary is invoked by bare name on PATH (argv[0] == "totchef"), but sudo's secure_path can't find a bare name. The re-exec must run the binary by its absolute sys.executable and pass only the user's args (argv[1:]) — never the bare argv[0]."""
    recipe_path = tmp_path / "recipe.toml"
    recipe_path.write_text('[bash.step]\napply = "true"\n')
    binary = "/home/op/.local/bin/totchef"  # absolute, as PyInstaller resolves sys.executable
    captured: dict = {}

    def capture_exec(target, argv):
        captured.update(argv=list(argv))
        raise SystemExit(0)  # sudo replaces the process — control never returns

    monkeypatch.setattr("os.geteuid", lambda: 1000)  # not root yet
    monkeypatch.setattr("os.execvp", capture_exec)
    monkeypatch.setattr("sys.frozen", True, raising=False)  # PyInstaller marks the onefile bundle frozen
    monkeypatch.setattr("sys.executable", binary)  # the bootloader resolves this to the absolute binary path
    monkeypatch.setattr("sys.argv", ["totchef", "up", "--recipe", str(recipe_path)])  # bare name, as the shell passes it via PATH
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    cli.run("up", "--recipe", str(recipe_path))

    relaunch = captured["argv"][2:]  # drop "sudo" and the "--preserve-env=..." flag
    assert relaunch[0] == binary  # sudo runs the binary by absolute path (found despite secure_path)
    assert "totchef" not in relaunch  # the bare argv[0] is never handed to sudo — not as a program, not as an arg
    assert relaunch[1:] == ["up", "--recipe", str(recipe_path)]  # only the user's original args follow


# 7.4 Distinguish recoverable failures from fatal ones


def test_7_4_1_hard_failure_aborts_the_apply_and_exits_1(recipe, terminal, totchef):
    """Hard failure aborts the apply and exits 1 (e.g. unavailable package, bash apply error, uv tool install failure)."""
    recipe.declares("bash", "broken", apply="false-cmd")
    recipe.declares("bash", "after", apply="echo done", depends_on=["bash.broken"])
    terminal.arrange("false-cmd", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_shows("bash.broken", "failed")
    terminal.expect_not_ran("echo done")  # apply aborted: the dependent never ran


def test_7_4_2_soft_failure_warns_finishes_and_exits_75(recipe, terminal, totchef, tmp_path):
    """Soft failure warns, finishes the run, exits 75 (e.g. snap refresh, post_hook, invalid JSON in a target file)."""
    target = tmp_path / "grub.cfg"
    recipe.declares("file", "grub", path=str(target), content="X\n", post_hook="update-grub-fails")
    recipe.declares("bash", "after", apply="echo done", depends_on=["file.grub"])
    terminal.arrange("update-grub-fails", exit_code=1)

    report = totchef.up()

    report.assert_soft_failed()
    report.assert_shows("file.grub", "post-failed")
    terminal.expect_ran("echo done")  # the run finished; the dependent still ran


def test_7_4_3_report_names_which_cooks_hard_or_soft_failed(recipe, terminal, totchef):
    """The end-of-run report names which cooks hard- or soft-failed."""
    recipe.declares("bash", "broken_step", apply="false-cmd")
    terminal.arrange("false-cmd", exit_code=1)

    report = totchef.up()

    report.assert_shows("bash.broken_step", "failed")
    assert "bash.broken_step" in report.report
    assert "failed" in report.report


def test_7_4_4_a_crash_outside_any_cook_still_reports_loudly(recipe, totchef, monkeypatch):
    """An unexpected exception after logs are redirected — a totchef bug, not a recipe failure — still exits 1 with the traceback in view, never a silent death."""
    recipe.declares("bash", "step", apply="true")

    def explode(config, dry_run):
        raise RuntimeError("scheduler bug")

    monkeypatch.setattr("totchef.cli.run_recipe", explode)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("RuntimeError")  # the full traceback scrolled past …
    report.assert_logged("scheduler bug")  # … naming the actual error


# 7.5 Skip steps that shouldn't run right now


def test_7_5_1_pre_hook_nonzero_exit_skips_the_item(recipe, terminal, totchef, tmp_path):
    """A non-zero pre_hook exit skips the item (reported as `skipped`, not failed)."""
    target = tmp_path / "f.conf"
    recipe.declares("file", "f", path=str(target), content="X\n", pre_hook="test -e /run/should-apply")
    terminal.arrange("test -e /run/should-apply", exit_code=1)

    report = totchef.up()

    report.assert_succeeded()  # a guarded skip is benign, not a failure
    report.assert_shows("file.f", "skipped")
    assert not target.exists()


def test_7_5_2_cooks_compose_intrinsic_guards_with_pre_hook(recipe, terminal, totchef, home):
    """Cooks chain their own guards with the operator's pre_hook (e.g. Chromium's "browser not running" check)."""
    local_state = home / ".config/chromium/Local State"
    local_state.parent.mkdir(parents=True)
    local_state.write_text('{"browser": {"enabled_labs_experiments": []}}')
    recipe.declares("chromium_flags", "chromium", local_state=".config/chromium/Local State", local_state_flags=["x@1"], pre_hook="test -e /run/maintenance")
    terminal.arrange("test -e /run/maintenance", exit_code=1)  # operator's own guard fails

    report = totchef.up()

    report.assert_shows("chromium_flags.chromium", "skipped")
    terminal.expect_ran("pgrep -x chromium")  # intrinsic guard and...
    terminal.expect_ran("test -e /run/maintenance")  # ...operator guard chained into one


def test_7_5_3_hooks_run_on_versioned_sections_too(recipe, terminal, http, totchef, system):
    """pre_hook/post_hook are valid on a versioned section too: the pre_hook gates the whole sync, the post_hook fires once after a change."""
    recipe.declares("cargo", packages=["ripgrep"], pre_hook="test -e /run/build-ok", post_hook="rebuild-completions")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    system.has("cargo", "cargo-binstall")
    terminal.arrange("cargo install --list", "")  # ripgrep absent → work pending
    terminal.arrange("test -e /run/build-ok", exit_code=1)  # but the pre_hook guard is unsatisfied

    totchef.lint().assert_valid()  # no longer rejected on a versioned section
    totchef.up().assert_shows("cargo.ripgrep", "skipped")
    terminal.expect_not_ran("cargo-binstall")  # guard gated the whole sync
    terminal.expect_not_ran("rebuild-completions")  # nothing changed → no post_hook

    terminal.reset()
    system.has("cargo", "cargo-binstall")
    terminal.arrange("cargo install --list", "")
    terminal.arrange("test -e /run/build-ok", "")  # now the guard passes
    terminal.arrange("cargo-binstall --no-confirm", effect=lambda: terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n"))

    totchef.up().assert_shows("cargo.ripgrep", "installed")
    terminal.expect_ran("rebuild-completions")  # the post_hook fired once after the change
