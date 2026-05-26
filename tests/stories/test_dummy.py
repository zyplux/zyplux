"""Dummy test demonstrating the prose style — delete once real stories land.

Note there are no imports: a test names the fixtures it needs (`recipe`, `terminal`,
`http`, `home`, `totchef`) and reads as the user story it covers. The only things
faked are the system boundaries (bash, network, home).

Every check is self-labelled:
- `expect_…` verifies what the system did at a mocked boundary (commands run, URLs
  fetched) — `terminal.expect_ran`, `terminal.expect_not_ran`, `http.expect_fetched`.
- `assert_…` (and the `assert` keyword) verifies real produced outcome/state — the
  report's actions, files on disk.
Arrange-only setup (`recipe.declares`, `terminal.arrange`, `http.arrange`) is not a
check.
"""


def test_plan_previews_a_bash_step_without_running_it(recipe, terminal, totchef):
    # User story 1.2 / 4.3: a dry run probes current state and reports "would apply",
    # but never runs the apply command.
    recipe.declares(
        "bash",
        "deep_sleep",
        current_state="cat /sys/power/mem_sleep",
        desired_state="deep",
        apply="echo deep > /sys/power/mem_sleep",
    )
    terminal.arrange("cat /sys/power/mem_sleep", "s2idle [deep]")

    plan = totchef.plan()

    plan.assert_shows("bash.deep_sleep", "would apply")
    plan.assert_succeeded()
    terminal.expect_ran("cat /sys/power/mem_sleep")
    terminal.expect_not_ran("echo deep")


def test_up_runs_the_apply_only_when_state_differs(recipe, terminal, totchef):
    # User story 1.1 / 6.1: state differs, so up runs the apply and reports "applied".
    recipe.declares(
        "bash",
        "deep_sleep",
        current_state="cat /sys/power/mem_sleep",
        desired_state="deep",
        apply="echo deep > /sys/power/mem_sleep",
    )
    terminal.arrange("cat /sys/power/mem_sleep", "s2idle [deep]")

    report = totchef.up()

    report.assert_report("""
        Report
        [1]{"cook-node",current,latest,action}:
          bash.deep_sleep,"s2idle [deep]",deep,applied
    """)
    terminal.expect_ran("echo deep > /sys/power/mem_sleep")


def test_up_is_idempotent_when_state_already_matches(recipe, terminal, totchef):
    # User story 6.1: current state already equals desired, so up makes no change.
    recipe.declares(
        "bash",
        "deep_sleep",
        current_state="cat /sys/power/mem_sleep",
        desired_state="deep",
        apply="echo deep > /sys/power/mem_sleep",
    )
    terminal.arrange("cat /sys/power/mem_sleep", "deep")

    report = totchef.up()

    report.assert_shows("bash.deep_sleep", "unchanged")
    terminal.expect_not_ran("echo deep")


def test_file_install_writes_then_is_idempotent(recipe, totchef, tmp_path):
    # User story 4.2 / 6.1: a [file] entry writes exact bytes to its `path` (pointed
    # at tmp_path here), and a second run sees the matching hash and changes nothing.
    target = tmp_path / "10-totchef.conf"
    recipe.declares("file", "grub_drop_in", path=str(target), content="GRUB_TIMEOUT=2\n")

    first = totchef.up()
    first.assert_shows("file.grub_drop_in", "applied")
    assert target.read_text() == "GRUB_TIMEOUT=2\n"

    second = totchef.up()
    second.assert_shows("file.grub_drop_in", "unchanged")


def test_settings_merges_env_under_home(recipe, totchef, home):
    # User story 5.3: [settings] merges settings_env into the JSON's `env` key. The
    # path is relative to $HOME, which the `home` fixture redirects to a temp dir.
    recipe.declares(
        "settings",
        "claude",
        settings_json=".claude/settings.json",
        settings_env={"DISABLE_TELEMETRY": "1"},
    )

    report = totchef.up()

    report.assert_shows("settings.claude", "applied")
    assert "DISABLE_TELEMETRY" in (home / ".claude/settings.json").read_text()


def test_plan_looks_up_the_latest_crate_version_over_http(recipe, http, totchef):
    # User story 3.3: the cargo plan looks up the latest version from crates.io. The
    # `http` fixture serves the response; an un-programmed URL would raise.
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    plan = totchef.plan()

    plan.assert_shows("cargo.ripgrep", "would install")
    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
