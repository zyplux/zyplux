"""User stories §11 — Managing dotfiles with chezmoi. One test per §11 criterion on the real chef in-process; only system boundaries (bash, network, host, home) are faked."""

# 11.1 Provision dotfiles from a git repo


def test_11_1_1_chezmoi_clones_the_repo_into_the_source_dir(recipe, system, terminal, totchef, chezmoi_cook):
    """`[chezmoi]` with a repo clones it into the source dir (`chezmoi init`) and never writes into $HOME — the flow is one-way, $HOME → repo."""
    system.has("chezmoi")
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    totchef.up().assert_shows("chezmoi.dotfiles", "applied")

    terminal.expect_ran("chezmoi init")
    terminal.expect_not_ran("chezmoi apply")


def test_11_1_2_source_dir_is_configurable_and_written_to_chezmoi_config(recipe, system, terminal, totchef, home, chezmoi_cook):
    """`source_dir` is passed to chezmoi (`--source`) and persisted as `sourceDir` (with a pinned `umask`) in ~/.config/chezmoi/chezmoi.toml so bare chezmoi commands agree and applied modes are deterministic."""
    system.has("chezmoi")
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git", source_dir="~/dotfiles")

    totchef.up().assert_succeeded()

    terminal.expect_ran(f"chezmoi init --source {home}/dotfiles")
    config = (home / ".config/chezmoi/chezmoi.toml").read_text()
    assert 'sourceDir = "~/dotfiles"' in config
    assert "umask = 0o022" in config


def test_11_1_3_chezmoi_is_idempotent_once_provisioned(recipe, system, terminal, totchef, home, chezmoi_cook):
    """A re-run is a no-op once the source is cloned, the config matches, and the capture timer is enabled: unchanged, no init or capture setup."""
    system.has("chezmoi")
    (home / ".local/share/chezmoi/.git").mkdir(parents=True)
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    totchef.up().assert_shows("chezmoi.dotfiles", "applied")

    terminal.reset()

    report = totchef.up()

    report.assert_shows("chezmoi.dotfiles", "unchanged")
    terminal.expect_not_ran("chezmoi init")
    terminal.expect_not_ran("systemctl --user start")


# 11.2 Run as the operator with the binary in place


def test_11_2_1_chezmoi_is_user_scoped_not_root(cli, chezmoi_repo, monkeypatch):
    """`[chezmoi]` manages the operator's $HOME, so the discovered custom cook lists with user scope (origin local) and never escalates to root."""
    monkeypatch.chdir(chezmoi_repo)
    monkeypatch.delenv("TOTCHEF_RECIPE", raising=False)

    cli.run("--list-cooks").assert_lists("chezmoi", scope="user", origin="local")


def test_11_2_2_chezmoi_without_the_binary_fails_clearly(recipe, totchef, chezmoi_cook):
    """With no chezmoi binary on PATH (the [url.chezmoi] installer hasn't run), the resource hard-fails naming the section that must run first."""
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("url.chezmoi")


# 11.3 Capture home edits back to the repo automatically


def test_11_3_1_auto_commit_and_push_are_on_and_written_to_chezmoi_git_config(recipe, system, totchef, home, chezmoi_cook):
    """The cook persists `autoCommit`/`autoPush` to the [git] section of chezmoi's config so the scheduled `chezmoi re-add` commits the captured changes and pushes them on its own."""
    system.has("chezmoi")
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    totchef.up().assert_succeeded()

    config = (home / ".config/chezmoi/chezmoi.toml").read_text()
    assert "[git]" in config
    assert "autoCommit = true" in config
    assert "autoPush = true" in config


def test_11_3_2_capture_units_install_and_the_timer_is_enabled(recipe, system, terminal, totchef, home, chezmoi_cook):
    """The cook installs the generated systemd *user* units into ~/.config/systemd/user and enables the timer by writing its timers.target.wants symlink (no session bus needed), then starts it."""
    system.has("chezmoi")
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    totchef.up().assert_shows("chezmoi.dotfiles", "applied")

    unit_dir = home / ".config/systemd/user"
    assert (unit_dir / "chezmoi-capture.service").exists()
    assert (unit_dir / "chezmoi-capture.timer").exists()
    assert (unit_dir / "timers.target.wants/chezmoi-capture.timer").is_symlink()
    terminal.expect_ran("systemctl --user start chezmoi-capture.timer")


def test_11_3_3_capture_is_idempotent_once_enabled(recipe, system, terminal, totchef, home, chezmoi_cook):
    """With the units installed and the timer enabled, a re-run shows unchanged: it neither rewrites the units nor re-runs `systemctl start`."""
    system.has("chezmoi")
    (home / ".local/share/chezmoi/.git").mkdir(parents=True)
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git")

    totchef.up().assert_shows("chezmoi.dotfiles", "applied")

    terminal.reset()

    report = totchef.up()

    report.assert_shows("chezmoi.dotfiles", "unchanged")
    terminal.expect_not_ran("systemctl --user start")


def test_11_3_4_timer_cadence_comes_from_timer_min(recipe, system, totchef, home, chezmoi_cook):
    """`timer_min` sets the timer's OnUnitActiveSec, so the operator tunes how often $HOME is captured."""
    system.has("chezmoi")
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git", timer_min=60)

    totchef.up().assert_succeeded()

    timer = (home / ".config/systemd/user/chezmoi-capture.timer").read_text()
    assert "OnUnitActiveSec=60min" in timer


def test_11_3_5_timer_min_must_be_positive(recipe, totchef, chezmoi_cook):
    """`timer_min` must be a positive number of minutes; 0 (or negative) is rejected at lint, since a zero-interval timer is invalid."""
    recipe.declares("chezmoi", repo="https://github.test/operator/dotfiles.git", timer_min=0)

    totchef.lint().assert_rejected("timer_min")
