"""User stories §5 — Configuring system state. One test per §5 criterion on the real chef in-process; only system boundaries (bash, network, host) are faked."""

# 4.1 Add third-party apt repositories securely


def test_5_1_1_apt_repo_fetches_key_dearmors_writes_keyring_and_sources(recipe, terminal, http, totchef, tmp_path):
    """`[apt_repo.<name>]` fetches the GPG key (de-armoring if needed), writes the keyring, and writes a deb822 .sources with `Signed-By:`."""
    keyring = tmp_path / "vendor.gpg"
    sources = tmp_path / "vendor.sources"
    recipe.declares(
        "apt_repo", "vendor", key_url="https://vendor.example/key.asc", uris="https://vendor.example/apt", keyring=str(keyring), source_path=str(sources)
    )
    http.arrange("vendor.example/key.asc", "-----BEGIN PGP PUBLIC KEY BLOCK-----\narmored\n-----END PGP PUBLIC KEY BLOCK-----\n")
    terminal.arrange("gpg --dearmor", "DEARMORED-KEY-BYTES")

    report = totchef.up()

    report.assert_shows("apt_repo.vendor", "applied")
    terminal.expect_ran("gpg --dearmor")
    assert keyring.read_bytes() == b"DEARMORED-KEY-BYTES"
    assert "Types: deb" in sources.read_text()
    assert f"Signed-By: {keyring}" in sources.read_text()


def test_5_1_2_operator_declares_key_url_uris_and_optional_fields(recipe, http, totchef, tmp_path):
    """Declares key_url and uris, with optional suites, components, architectures, and custom keyring/source_path."""
    keyring = tmp_path / "vendor.gpg"
    sources = tmp_path / "vendor.sources"
    recipe.declares(
        "apt_repo",
        "vendor",
        key_url="https://vendor.example/key",
        uris="https://vendor.example/apt",
        suites="noble",
        components="main universe",
        architectures="amd64",
        keyring=str(keyring),
        source_path=str(sources),
    )
    http.arrange("vendor.example/key", "raw-binary-key")

    totchef.up().assert_succeeded()

    text = sources.read_text()
    assert "URIs: https://vendor.example/apt" in text
    assert "Suites: noble" in text
    assert "Components: main universe" in text
    assert "Architectures: amd64" in text
    assert keyring.read_bytes() == b"raw-binary-key"


def test_5_1_3_suites_release_placeholder_substituted_with_codename(recipe, http, totchef, system, tmp_path):
    """`{release}` in `suites` is substituted with the detected Ubuntu codename."""
    keyring = tmp_path / "vendor.gpg"
    sources = tmp_path / "vendor.sources"
    recipe.declares("apt_repo", "vendor", key_url="https://v/key", uris="https://v/apt", suites="{release}", keyring=str(keyring), source_path=str(sources))
    http.arrange("v/key", "raw-key")
    system.running_release("plucky")

    totchef.up().assert_succeeded()

    assert "Suites: plucky" in sources.read_text()


def test_5_1_4_repo_configured_only_when_keyring_and_sources_both_exist(recipe, totchef, tmp_path):
    """Configured only when both the keyring and the .sources file exist; otherwise re-applied."""
    keyring = tmp_path / "vendor.gpg"
    sources = tmp_path / "vendor.sources"
    keyring.write_bytes(b"key")  # only the keyring exists so far
    recipe.declares("apt_repo", "vendor", key_url="https://v/key", uris="https://v/apt", keyring=str(keyring), source_path=str(sources))

    totchef.plan().assert_shows("apt_repo.vendor", "would apply")

    sources.write_text("Types: deb\n")  # now both exist

    totchef.plan().assert_shows("apt_repo.vendor", "ok")


# 4.2 Install files with exact content


def test_5_2_1_file_writes_from_content_or_bundled_source_with_mode(recipe, scenario, chef, totchef, tmp_path):
    """`[file.<name>]` writes from inline content or a bundled source asset with a mode; exactly one of content/source must be set."""
    inline = tmp_path / "drop.conf"
    bundled = tmp_path / "write-if-changed.py"
    recipe.declares("file", "drop", path=str(inline), content="X=1\n", mode="0600")
    recipe.declares("file", "script", path=str(bundled), source="write-if-changed.py")

    totchef.up().assert_succeeded()

    assert inline.read_text() == "X=1\n"
    assert (inline.stat().st_mode & 0o777) == 0o600
    assert bundled.read_bytes()  # copied verbatim from the bundled asset

    both = scenario().declares("file", "x", path=str(inline), content="a", source="write-if-changed.py")
    chef(both).lint().assert_rejected()  # exactly one of content/source must be set


def test_5_2_2_file_diffed_by_content_hash(recipe, totchef, tmp_path):
    """The file is diffed by content hash, rewritten only when bytes differ."""
    target = tmp_path / "f"
    recipe.declares("file", "f", path=str(target), content="A\n")

    totchef.up().assert_shows("file.f", "applied")
    totchef.up().assert_shows("file.f", "unchanged")

    recipe.config["file"]["f"]["content"] = "B\n"
    totchef.up().assert_shows("file.f", "applied")


def test_5_2_3_post_hook_runs_only_when_the_file_changed(recipe, terminal, totchef, tmp_path):
    """A post_hook (e.g. update-grub, daemon-reload) runs only when the file changed."""
    target = tmp_path / "grub.cfg"
    recipe.declares("file", "grub", path=str(target), content="GRUB_TIMEOUT=2\n", post_hook="update-grub")

    totchef.up().assert_shows("file.grub", "applied")
    terminal.expect_ran("update-grub")

    terminal.reset()
    totchef.up().assert_shows("file.grub", "unchanged")
    terminal.expect_not_ran("update-grub")


def test_5_2_4_file_is_privilege_agnostic_root_per_entry(recipe, totchef, cli, tmp_path):
    """Privilege-agnostic: set needs_root per entry for files under /etc, /usr, etc."""
    cli.run("--list-cooks").assert_lists("file", scope="user")  # the cook itself is privilege-agnostic

    recipe.declares("file", "etc_file", path=str(tmp_path / "etc_file"), content="a", needs_root=True)
    recipe.declares("file", "user_file", path=str(tmp_path / "user_file"), content="b")

    totchef.lint().assert_valid()  # the per-entry root grant is accepted

    plan = totchef.plan()
    plan.assert_shows("file.etc_file", "would apply")  # the granted entry plans …
    plan.assert_shows("file.user_file", "would apply")  # … alongside the ungranted sibling

    # the grant actually escalating only that entry is verified end-to-end in the container — test_6_3_2


# 4.3 Run arbitrary idempotent shell steps


def test_5_3_1_bash_skips_apply_when_current_state_equals_desired(recipe, terminal, totchef):
    """totchef runs current_state; if its output equals desired_state the step is skipped, otherwise apply runs."""
    recipe.declares("bash", "pin", current_state="cat /etc/apt/preferences.d/pin", desired_state="Pin: release o=vendor", apply="install-pin")
    terminal.arrange("cat /etc/apt/preferences.d/pin", "Pin: release o=vendor")

    totchef.up().assert_shows("bash.pin", "unchanged")
    terminal.expect_not_ran("install-pin")

    terminal.arrange("cat /etc/apt/preferences.d/pin", "")  # drift: probe no longer matches

    totchef.up().assert_shows("bash.pin", "applied")
    terminal.expect_ran("install-pin")


def test_5_3_2_bash_with_no_current_state_always_applies(recipe, terminal, totchef):
    """With no current_state, the step is "no check" and always applies."""
    recipe.declares("bash", "always", apply="run-it")

    totchef.up().assert_shows("bash.always", "applied")
    terminal.expect_ran("run-it")


def test_5_3_3_bash_guarded_steps_are_no_ops_on_rerun(recipe, terminal, totchef):
    """Used for pinning / preseed / prereqs, each guarded by a cheap state probe so re-runs are no-ops."""
    recipe.declares("bash", "preseed", current_state="debconf-show ttf-mscorefonts", desired_state="accepted", apply="debconf-set-selections")
    terminal.arrange("debconf-show ttf-mscorefonts", "accepted")

    totchef.up().assert_shows("bash.preseed", "unchanged")
    totchef.up().assert_shows("bash.preseed", "unchanged")
    terminal.expect_not_ran("debconf-set-selections")


def test_5_3_4_bash_is_privilege_agnostic_root_per_entry(recipe, totchef, cli):
    """Privilege-agnostic: grant root per entry."""
    cli.run("--list-cooks").assert_lists("bash", scope="user")  # the cook itself is privilege-agnostic

    recipe.declares("bash", "root_step", apply="x", needs_root=True)
    recipe.declares("bash", "user_step", apply="y")

    totchef.lint().assert_valid()  # the per-entry root grant is accepted

    plan = totchef.plan()
    plan.assert_shows("bash.root_step", "would apply")  # the granted entry plans …
    plan.assert_shows("bash.user_step", "would apply")  # … alongside the ungranted sibling

    # the grant actually escalating only that entry is verified end-to-end in the container — test_6_3_2
