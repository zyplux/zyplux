"""User stories §3 — Managing packages (versioned domains).

One prose-style test per acceptance criterion in `user-stories.md` §3. Each drives
the real chef in-process; only the system boundaries (bash, network, host) are faked.
"""

from framework import RecipeBuilder, Totchef
from totchef.recipe_graph import build_node_graph, build_nodes

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
    """A package with apt-cache policy priority 0 fails fast with guidance (naming,
    component, or missing [apt_repo])."""
    recipe.declares("apt_pkg", packages=["totally-fake"])
    terminal.arrange("apt-cache policy totally-fake", "totally-fake:\n  Installed: (none)\n  Candidate: (none)\n")

    report = totchef.up()

    report.assert_hard_failed()
    assert "not available in any configured repo" in report.results["apt_pkg"].message
    terminal.expect_not_ran("nala full-upgrade")
    terminal.expect_not_ran("nala install")


def test_3_1_3_apt_pkg_runs_as_root_after_prereqs_and_repos(recipe):
    """Runs as root; depends on apt prereqs and repos being in place first."""
    recipe.declares("apt_pkg", packages=["git"], depends_on=["bash", "apt_repo"])
    recipe.declares("bash", "apt_prereqs", apply="true")
    recipe.declares("apt_repo", "vendor", key_url="https://x/key", uris="https://x")

    nodes = build_nodes(recipe.config)
    graph = build_node_graph(nodes)

    assert nodes["apt_pkg"].needs_root is True
    assert {"bash.apt_prereqs", "apt_repo.vendor"} <= graph["apt_pkg"]


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


def test_3_2_2_snap_install_failure_hard_refresh_failure_soft(terminal, system):
    """An install failure is hard; a refresh failure is soft (snap still usable)."""
    system.has("snap")
    terminal.arrange("snap list", "Name  Version\n")
    terminal.arrange("snap refresh --list", "")
    terminal.arrange("snap install nonesuch", exit_code=1)
    install = Totchef(RecipeBuilder().declares("snap", packages=["nonesuch"]), terminal)

    hard = install.up()

    hard.assert_hard_failed()
    assert "snap install failed" in hard.results["snap"].message

    terminal.reset()
    system.has("snap")
    terminal.arrange("snap list", "Name     Version\nslack    4.0\n")
    terminal.arrange("snap refresh --list", "Name   Version\nslack  4.1\n")
    terminal.arrange("snap refresh slack", exit_code=1)
    refresh = Totchef(RecipeBuilder().declares("snap", packages=["slack"]), terminal)

    soft = refresh.up()

    soft.assert_soft_failed()
    assert "snap refresh failed" in soft.results["snap"].message


def test_3_2_3_missing_snapd_is_a_hard_failure(recipe, totchef):
    """If snapd isn't present, asking to install a snap is a hard failure with a
    clear message."""
    recipe.declares("snap", packages=["code"])

    report = totchef.up()

    report.assert_hard_failed()
    assert "snapd is not installed" in report.results["snap"].message


# 3.3 Install and update Rust crates


def test_3_3_1_cargo_installs_via_binstall(recipe, terminal, http, totchef, system):
    """`[cargo]` installs via `cargo binstall` (one batched command that skips
    already-current crates)."""
    recipe.declares("cargo", packages=["ripgrep"])
    system.has("cargo", "cargo-binstall")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "")
    terminal.arrange("cargo-binstall --no-confirm", effect=lambda: terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n    rg\n"))

    report = totchef.up()

    report.assert_shows("cargo.ripgrep", "installed")
    terminal.expect_ran("cargo-binstall --no-confirm ripgrep")


def test_3_3_2_cargo_binstall_is_bootstrapped_once_if_missing(recipe, terminal, http, totchef, system):
    """If cargo-binstall is missing, it's bootstrapped once via `cargo install`."""
    recipe.declares("cargo", packages=["ripgrep"])
    system.has("cargo")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "")
    terminal.arrange("cargo install cargo-binstall", effect=lambda: system.has("cargo-binstall"))
    terminal.arrange("cargo-binstall --no-confirm", effect=lambda: terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n"))

    report = totchef.up()

    report.assert_succeeded()
    assert terminal.count("cargo install cargo-binstall") == 1


def test_3_3_3_missing_cargo_fails_hard_pointing_at_url_rustup(recipe, http, totchef):
    """If cargo is missing the run fails hard, telling the operator the [url] rustup
    install must run first."""
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    report = totchef.up()

    report.assert_hard_failed()
    assert "rustup" in report.results["cargo"].message


def test_3_3_4_latest_crate_versions_looked_up_concurrently(recipe, http, totchef):
    """Latest versions are looked up concurrently from crates.io for the plan."""
    recipe.declares("cargo", packages=["ripgrep", "just"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    http.arrange("crates.io/api/v1/crates/just", '{"crate": {"max_stable_version": "1.40.0"}}')

    plan = totchef.plan()

    plan.assert_shows("cargo.ripgrep", "would install")
    plan.assert_shows("cargo.just", "would install")
    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
    http.expect_fetched("crates.io/api/v1/crates/just")


# 3.4 Install and upgrade Python CLI tools


def test_3_4_1_uv_installs_and_upgrades_each_tool_concurrently(recipe, terminal, http, totchef, system):
    """`[uv]` installs/upgrades each tool via uv, run concurrently behind uv's locks."""
    recipe.declares("uv", packages=["ruff", "pyright"])
    system.has("uv")
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/pyright/json", '{"info": {"version": "1.1.380"}}')
    terminal.arrange("uv tool list", "ruff v0.5.0\n")

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("uv tool upgrade ruff")
    terminal.expect_ran("uv tool install pyright")


def test_3_4_2_uv_failure_reports_hard_naming_the_failed_tools(recipe, terminal, http, totchef, system):
    """If any tool fails, the run reports a hard failure naming the failed tools."""
    recipe.declares("uv", packages=["ruff", "brokentool"])
    system.has("uv")
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/brokentool/json", '{"info": {"version": "1.0"}}')
    terminal.arrange("uv tool list", "")
    terminal.arrange("uv tool install brokentool", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    assert "brokentool" in report.results["uv"].message


def test_3_4_3_uv_requires_uv_and_looks_up_latest_from_pypi(recipe, http, totchef):
    """Requires uv to be present; latest versions looked up concurrently from PyPI."""
    recipe.declares("uv", packages=["ruff"])
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')

    plan = totchef.plan()

    plan.assert_shows("uv.ruff", "would install")
    http.expect_fetched("pypi.org/pypi/ruff/json")

    report = totchef.up()

    report.assert_hard_failed()
    assert "[url]" in report.results["uv"].message


# 3.5 Bootstrap vendor CLIs from their official installers


def test_3_5_1_url_fetches_installer_pipes_to_bash_diffs_presence(recipe, terminal, http, totchef, system):
    """`[url.<name>]` fetches an installer URL and pipes it to bash; presence (not
    version) is diffed."""
    recipe.declares("url", "bun", url="https://bun.sh/install")
    http.arrange("bun.sh/install", "#!/bin/bash\necho installing bun")
    terminal.arrange("bash -s --", effect=lambda: system.has("bun"))
    terminal.arrange("bun --version", "1.1.0")

    report = totchef.up()

    report.assert_shows("url.bun", "installed")
    http.expect_fetched("bun.sh/install")
    terminal.expect_ran("bash -s --")
    assert terminal.stdin_for("bash -s --") == b"#!/bin/bash\necho installing bun"


def test_3_5_2_binary_name_defaults_to_entry_name_overridable_with_bin(recipe, terminal, http, totchef, system):
    """The binary name defaults to the entry name but can be overridden with `bin`."""
    recipe.declares("url", "claude", url="https://claude.ai/install.sh", bin="claude-code")
    http.arrange("claude.ai/install.sh", "#!/bin/sh")
    terminal.arrange("bash -s --", effect=lambda: system.has("claude-code"))
    terminal.arrange("claude-code --version", "2.1.0")

    report = totchef.up()

    report.assert_shows("url.claude", "installed")
    terminal.expect_ran("claude-code --version")


def test_3_5_3_update_action_arg_list_rerun_installer_or_absent(terminal, http, system):
    """update_action: an arg list run against the binary, "rerun-installer", or absent."""
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    http.arrange("bun.sh/install", "#!/bin/bash")

    arg_list = Totchef(RecipeBuilder().declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"]), terminal)
    arg_list.up().assert_succeeded()
    terminal.expect_ran("bun upgrade")
    terminal.expect_not_ran("bash -s --")

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    http.arrange("bun.sh/install", "#!/bin/bash")
    rerun = Totchef(RecipeBuilder().declares("url", "bun", url="https://bun.sh/install", update_action="rerun-installer"), terminal)
    rerun.up().assert_succeeded()
    terminal.expect_ran("bash -s --")

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    absent = Totchef(RecipeBuilder().declares("url", "bun", url="https://bun.sh/install"), terminal)
    absent.up().assert_succeeded()
    terminal.expect_not_ran("bash -s --")
    terminal.expect_not_ran("bun upgrade")


def test_3_5_4_update_guard_runs_before_updating(recipe, terminal, totchef, system):
    """An optional update_guard shell snippet runs before updating."""
    recipe.declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"], update_guard="pkill -f bun-server")
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("pkill -f bun-server")
    terminal.expect_ran("bun upgrade")


def test_3_5_5_url_install_failure_hard_update_failure_soft(terminal, http, system):
    """Install failure is hard, update failure is soft (the tool stays installed)."""
    http.arrange("bun.sh/install", "#!/bin/bash")
    terminal.arrange("bash -s --", exit_code=1)
    install = Totchef(RecipeBuilder().declares("url", "bun", url="https://bun.sh/install"), terminal)

    hard = install.up()

    hard.assert_hard_failed()
    assert "install failed" in hard.results["url.bun"].message

    terminal.reset()
    system.has("bun")
    terminal.arrange("bun --version", "1.1.0")
    terminal.arrange("bun upgrade", exit_code=1)
    update = Totchef(RecipeBuilder().declares("url", "bun", url="https://bun.sh/install", update_action=["upgrade"]), terminal)

    soft = update.up()

    soft.assert_soft_failed()
    assert "update failed" in soft.results["url.bun"].message


def test_3_5_6_version_best_effort_parsed_falls_back_to_present(recipe, terminal, totchef, system):
    """Version is best-effort parsed from --version; unparseable reports `present`."""
    recipe.declares("url", "bun", url="https://bun.sh/install")
    system.has("bun")
    terminal.arrange("bun --version", "bun: a fast runtime")

    report = totchef.up()

    report.assert_shows("url.bun", "unchanged")
    assert report.results["url.bun"].rows[0].installed == "present"
