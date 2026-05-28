"""User stories §3 — Managing packages. One test per §3 criterion on the real chef in-process; only system boundaries (bash, network, host) are faked."""

# A package's `apt-cache policy` output, before and after installation. Priority 500
# (a real version-table entry) keeps it out of the "not in any repo" fail-fast path.
POLICY_ABSENT = "git:\n  Installed: (none)\n  Candidate: 1:2.40-1\n  Version table:\n     1:2.40-1 500\n        500 http://archive.ubuntu.com/ubuntu noble/main amd64 Packages\n"
POLICY_PRESENT = "git:\n  Installed: 1:2.40-1\n  Candidate: 1:2.40-1\n  Version table:\n *** 1:2.40-1 500\n        500 http://archive.ubuntu.com/ubuntu noble/main amd64 Packages\n"


# 3.1 Install and upgrade apt packages


def test_3_1_1_apt_pkg_installed_via_nala_full_transaction(recipe, terminal, totchef):
    """`[apt_pkg]` installs/upgrades via nala (update, full-upgrade, install, autoremove)."""
    recipe.declares("apt_pkg", packages=["git"])
    terminal.arrange("apt-cache policy git", POLICY_ABSENT)
    terminal.arrange("nala install", effect=lambda: terminal.arrange("apt-cache policy git", POLICY_PRESENT))

    report = totchef.up()

    report.assert_shows("apt_pkg.git", "installed")
    report.assert_succeeded()
    terminal.expect_ran("nala update")
    terminal.expect_ran("nala full-upgrade")
    terminal.expect_ran("nala install -y git")
    terminal.expect_ran("nala autoremove")


def test_3_1_2_priority_zero_package_fails_fast_with_guidance(recipe, terminal, totchef):
    """A package with apt-cache policy priority 0 fails fast with guidance (naming, component, or missing [apt_repo])."""
    recipe.declares("apt_pkg", packages=["totally-fake"])
    terminal.arrange("apt-cache policy totally-fake", "totally-fake:\n  Installed: (none)\n  Candidate: (none)\n")

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("not available in any configured repo")
    terminal.expect_not_ran("nala full-upgrade")
    terminal.expect_not_ran("nala install")


def test_3_1_3_apt_pkg_runs_as_root_after_prereqs_and_repos(recipe, terminal, totchef, cli):
    """Runs as root; depends on apt prereqs and repos being in place first."""
    recipe.declares("apt_pkg", packages=["git"], depends_on=["bash", "apt_repo"])
    recipe.declares("bash", "apt_prereqs", apply="true")
    recipe.declares("apt_repo", "vendor", key_url="https://x/key", uris="https://x")
    terminal.arrange("apt-cache policy git", POLICY_ABSENT)

    cli.run("--list-cooks").assert_lists("apt_pkg", scope="root")  # runs as root

    plan = totchef.plan()
    plan.assert_ran_before("bash.apt_prereqs", "apt_pkg.git")  # after the prereqs
    plan.assert_ran_before("apt_repo.vendor", "apt_pkg.git")  # after the repos


# 3.2 Install and refresh snaps


def test_3_2_1_snap_installs_missing_and_refreshes_installed(recipe, terminal, totchef, system):
    """`[snap]` installs missing snaps and refreshes installed ones."""
    recipe.declares("snap", packages=["code", "firefox"])
    system.has("snap")
    terminal.arrange("snap list", "Name     Version  Rev  Tracking  Publisher  Notes\nfirefox  120.0    100  latest    mozilla    -\n")
    terminal.arrange("snap refresh --list", "Name     Version  Rev  Publisher  Notes\nfirefox  121.0    101  mozilla    -\n")

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("snap install code")
    terminal.expect_ran("snap refresh firefox")
    terminal.expect_not_ran("snap install firefox")
    terminal.expect_not_ran("snap refresh code")


def test_3_2_2_snap_install_failure_hard_refresh_failure_soft(scenario, chef, terminal, system):
    """An install failure is hard; a refresh failure is soft (snap still usable)."""
    system.has("snap")
    terminal.arrange("snap list", "Name  Version\n")
    terminal.arrange("snap refresh --list", "")
    terminal.arrange("snap install nonesuch", exit_code=1)
    install = scenario().declares("snap", packages=["nonesuch"])

    hard = chef(install).up()

    hard.assert_hard_failed()
    hard.assert_logged("snap install failed")

    terminal.reset()
    system.has("snap")
    terminal.arrange("snap list", "Name     Version\nslack    4.0\n")
    terminal.arrange("snap refresh --list", "Name   Version\nslack  4.1\n")
    terminal.arrange("snap refresh slack", exit_code=1)
    refresh = scenario().declares("snap", packages=["slack"])

    soft = chef(refresh).up()

    soft.assert_soft_failed()
    soft.assert_logged("snap refresh failed")


def test_3_2_3_missing_snapd_is_a_hard_failure(recipe, totchef):
    """If snapd isn't present, asking to install a snap is a hard failure with a clear message."""
    recipe.declares("snap", packages=["code"])

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("snapd is not installed")


# 3.3 Bootstrap vendor CLIs from their official installers


def test_3_3_1_url_fetches_installer_pipes_to_bash_diffs_presence(recipe, terminal, http, totchef, system):
    """`[url.<name>]` fetches an installer URL and pipes it to bash; presence (not version) is diffed."""
    recipe.declares("url", "bun", url="https://bun.sh/install")
    http.arrange("bun.sh/install", "#!/bin/bash\necho installing bun")
    terminal.arrange("bash -s --", effect=lambda: system.has("bun"))
    terminal.arrange("bun --version", "1.1.0")

    report = totchef.up()

    report.assert_shows("url.bun", "installed")
    http.expect_fetched("bun.sh/install")
    terminal.expect_ran("bash -s --")
    assert terminal.stdin_for("bash -s --") == b"#!/bin/bash\necho installing bun"


def test_3_3_2_binary_name_defaults_to_entry_name_overridable_with_bin(recipe, terminal, http, totchef, system):
    """The binary name defaults to the entry name but can be overridden with `bin`."""
    recipe.declares("url", "claude", url="https://claude.ai/install.sh", bin="claude-code")
    http.arrange("claude.ai/install.sh", "#!/bin/sh")
    terminal.arrange("bash -s --", effect=lambda: system.has("claude-code"))
    terminal.arrange("claude-code --version", "2.1.0")

    report = totchef.up()

    report.assert_shows("url.claude", "installed")
    terminal.expect_ran("claude-code --version")


def test_3_3_3_update_action_arg_list_rerun_installer_or_absent(scenario, chef, terminal, http, system):
    """update_action: an arg list run against the binary, "rerun-installer", or absent."""
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    http.arrange("bun.sh/install", "#!/bin/bash")

    arg_list = scenario().declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"])
    chef(arg_list).up().assert_succeeded()
    terminal.expect_ran("bun upgrade")
    terminal.expect_not_ran("bash -s --")

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    http.arrange("bun.sh/install", "#!/bin/bash")
    rerun = scenario().declares("url", "bun", url="https://bun.sh/install", update_action="rerun-installer")
    chef(rerun).up().assert_succeeded()
    terminal.expect_ran("bash -s --")

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    absent = scenario().declares("url", "bun", url="https://bun.sh/install")
    chef(absent).up().assert_succeeded()
    terminal.expect_not_ran("bash -s --")
    terminal.expect_not_ran("bun upgrade")


def test_3_3_4_update_guard_runs_before_updating(recipe, terminal, totchef, system):
    """An optional update_guard shell snippet runs before updating."""
    recipe.declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"], update_guard="pkill -f bun-server")
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("pkill -f bun-server")
    terminal.expect_ran("bun upgrade")
    order = [command.line for command in terminal.commands]
    guarded = next(i for i, line in enumerate(order) if "pkill -f bun-server" in line)
    updated = next(i for i, line in enumerate(order) if "bun upgrade" in line)
    assert guarded < updated  # the guard quiesced the server before the binary was replaced


def test_3_3_5_url_install_failure_hard_update_failure_soft(scenario, chef, terminal, http, system):
    """Install failure is hard, update failure is soft (the tool stays installed)."""
    http.arrange("bun.sh/install", "#!/bin/bash")
    terminal.arrange("bash -s --", exit_code=1)
    install = scenario().declares("url", "bun", url="https://bun.sh/install")

    hard = chef(install).up()

    hard.assert_hard_failed()
    hard.assert_logged("install failed")

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    terminal.arrange("bun upgrade", exit_code=1)
    update = scenario().declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"])

    soft = chef(update).up()

    soft.assert_soft_failed()
    soft.assert_logged("update failed")


def test_3_3_6_version_best_effort_parsed_falls_back_to_present(recipe, terminal, totchef, system):
    """Version is best-effort parsed from --version; unparseable reports `present`."""
    recipe.declares("url", "bun", url="https://bun.sh/install")
    system.has("bun")
    terminal.arrange("bun --version", "bun: a fast runtime")

    plan = totchef.plan()

    plan.assert_shows("url.bun", "would sync")
    assert "present" in next(line for line in plan.report.splitlines() if "url.bun" in line)  # version parsed best-effort

    totchef.up().assert_shows("url.bun", "unchanged")  # and an actual run sees it's already present
