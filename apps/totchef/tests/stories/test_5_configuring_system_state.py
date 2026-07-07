"""User stories §5 — Configuring system state. One test per §5 criterion on the real chef in-process; only system boundaries (bash, network, host) are faked."""

# 5.1 Add third-party apt repositories securely


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


def test_5_1_5_relative_urls_resolve_against_the_repo_url(recipe, scenario, chef, apt_keyrings_dir, apt_sources_dir, http, totchef):
    """Relative `key_url`/`uris` — or an omitted `uris` — resolve against `url` (scheme optional, https assumed); the files keep the entry's name; a relative URL without `url` is rejected."""
    recipe.declares("apt_repo", "vendor", url="vendor.example/apt", key_url="key.gpg")
    http.arrange("https://vendor.example/apt/key.gpg", "raw-key")

    totchef.up().assert_succeeded()

    keyring = apt_keyrings_dir / "vendor.gpg"
    assert keyring.read_bytes() == b"raw-key"
    sources_text = (apt_sources_dir / "vendor.sources").read_text()
    assert "URIs: https://vendor.example/apt" in sources_text
    assert f"Signed-By: {keyring}" in sources_text

    baseless = scenario().declares("apt_repo", "vendor", key_url="key.gpg")
    chef(baseless).lint().assert_rejected("set `url` or absolute URLs")


def test_5_1_6_pin_priority_writes_origin_pin_into_preferences(recipe, http, totchef, tmp_path):
    """`pin_priority` writes `/etc/apt/preferences.d/<name>.pref` pinning the repo's origin host (derived from `uris`) to that priority, so a package it ships can outrank the Ubuntu-archive pin; the repo counts as configured only once that pref also exists."""
    keyring = tmp_path / "vendor.gpg"
    sources = tmp_path / "vendor.sources"
    prefs = tmp_path / "vendor.pref"
    recipe.declares(
        "apt_repo",
        "vendor",
        key_url="https://cli.github.test/key",
        uris="https://cli.github.test/packages",
        keyring=str(keyring),
        source_path=str(sources),
        preferences_path=str(prefs),
        pin_priority=1001,
    )
    http.arrange("cli.github.test/key", "raw-key")

    totchef.up().assert_succeeded()

    pin = prefs.read_text()
    assert "Package: *" in pin
    assert "Pin: origin cli.github.test" in pin
    assert "Pin-Priority: 1001" in pin

    prefs.unlink()  # the pin is gone on disk → drift, even though keyring + sources remain
    totchef.plan().assert_shows("apt_repo.vendor", "would apply")


# 5.2 Install files with exact content


def test_5_2_1_file_writes_from_content_or_bundled_source_with_mode(recipe, scenario, chef, bundled_files, totchef, tmp_path):
    """`[file.<name>]` writes from inline content or a bundled source asset beside the recipe with a mode; setting both is rejected."""
    (bundled_files / "asset.txt").write_text("bundled-bytes\n")
    inline = tmp_path / "drop.conf"
    copied = tmp_path / "copied.txt"
    recipe.declares("file", "drop", path=str(inline), content="X=1\n", mode="0600")
    recipe.declares("file", "script", path=str(copied), source="asset.txt")

    totchef.up().assert_succeeded()

    assert inline.read_text() == "X=1\n"
    assert (inline.stat().st_mode & 0o777) == 0o600
    assert copied.read_text() == "bundled-bytes\n"  # copied verbatim from the bundled asset

    both = scenario().declares("file", "x", path=str(inline), content="a", source="asset.txt")
    chef(both).lint().assert_rejected()  # content and source together are rejected


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


def test_5_2_4_file_path_expands_tilde_for_per_user_installs(recipe, home, totchef):
    """A `~` in path resolves against `$HOME`, so per-user entries stay portable across machines."""
    recipe.declares("file", "tool", path="~/.local/bin/tool", content="#!/usr/bin/env python3\n", mode="0755")

    totchef.up().assert_shows("file.tool", "applied")

    installed = home / ".local/bin/tool"
    assert installed.read_text() == "#!/usr/bin/env python3\n"
    assert (installed.stat().st_mode & 0o777) == 0o755


def test_5_2_5_file_is_privilege_agnostic_root_per_entry(recipe, totchef, cli, tmp_path):
    """Privilege-agnostic: set needs_root per entry for files under /etc, /usr, etc."""
    cli.run("--list-cooks").assert_lists("file", scope="user")  # the cook itself is privilege-agnostic

    recipe.declares("file", "etc_file", path=str(tmp_path / "etc_file"), content="a", needs_root=True)
    recipe.declares("file", "user_file", path=str(tmp_path / "user_file"), content="b")

    totchef.lint().assert_valid()  # the per-entry root grant is accepted

    plan = totchef.plan()
    plan.assert_shows("file.etc_file", "would apply")  # the granted entry plans …
    plan.assert_shows("file.user_file", "would apply")  # … alongside the ungranted sibling

    # the grant actually escalating only that entry is verified end-to-end in the container — test_6_3_2


def test_5_2_6_source_defaults_to_the_bundled_file_named_after_the_entry(recipe, scenario, chef, bundled_files, totchef, tmp_path):
    """With neither `content` nor `source`, the entry installs the unique bundled file whose stem matches the entry name; zero or several matches fail lint asking for an explicit `source`."""
    (bundled_files / "motd.txt").write_text("welcome\n")
    target = tmp_path / "motd"
    recipe.declares("file", "motd", path=str(target))

    totchef.up().assert_shows("file.motd", "applied")
    assert target.read_text() == "welcome\n"

    (bundled_files / "motd.conf").write_text("rival\n")
    totchef.lint().assert_rejected("set `source` explicitly")  # two bundled stems now match — ambiguous

    ghost = scenario().declares("file", "ghost", path=str(target))
    chef(ghost).lint().assert_rejected("no bundled file")


# 5.3 Run arbitrary idempotent shell steps


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


# 5.4 Install versioned commands onto the PATH


def test_5_4_1_usr_local_bin_and_local_bin_install_command_named_after_source_stem(recipe, home, usr_local_bin_dir, bundled_files, totchef):
    """`[usr_local_bin.<name>]` installs a bundled script to /usr/local/bin and `[local_bin.<name>]` to ~/.local/bin — mode 0755, command named after the source stem, only `source` declared."""
    command = '#!/bin/bash\n__version__="1.0.0"\ncase "$1" in --version) echo "$__version__";; --help) echo usage;; esac\n'
    (bundled_files / "write-if-changed.py").write_text(command)
    (bundled_files / "ctop.py").write_text(command)
    recipe.declares("usr_local_bin", "write_if_changed", source="write-if-changed.py")
    recipe.declares("local_bin", "ctop", source="ctop.py")

    totchef.up().assert_succeeded()

    system_command = usr_local_bin_dir / "write-if-changed"
    user_command = home / ".local/bin/ctop"
    assert system_command.read_text().startswith("#!")  # the bundled asset, copied verbatim
    assert user_command.read_text().startswith("#!")
    assert (system_command.stat().st_mode & 0o777) == 0o755
    assert (user_command.stat().st_mode & 0o777) == 0o755


def test_5_4_2_version_decides_the_update_not_content(recipe, home, bundled_files, totchef):
    """The diff key is the command's embedded `__version__`: an older install is rewritten, equal versions leave differing bytes alone, and the report columns carry the versions."""
    bash_tool = '#!/bin/bash\n__version__="2.0.0"\ncase "$1" in --version) echo "$__version__";; --help) echo "usage: tool";; esac\n'
    (bundled_files / "tool.sh").write_text(bash_tool)
    installed = home / ".local/bin/tool"
    installed.parent.mkdir(parents=True)
    installed.write_text('#!/bin/bash\n__version__="1.0.0"\n')
    recipe.declares("local_bin", "tool", source="tool.sh")

    report = totchef.up()

    report.assert_shows("local_bin.tool", "applied")
    assert "local_bin.tool,1.0.0,2.0.0,2.0.0,applied" in report.full_table  # before/current/latest read as versions
    assert installed.read_text() == bash_tool

    installed.write_text(installed.read_text() + "# local tweak\n")  # same version, different bytes

    totchef.up().assert_shows("local_bin.tool", "unchanged")
    assert "# local tweak" in installed.read_text()  # equal versions never reinstall


def test_5_4_3_command_may_be_any_language_even_a_binary(recipe, home, bundled_files, totchef):
    """The contract markers are read off the file's bytes, so a compiled binary qualifies — embed `__version__ = "<version>"` as a constant string."""
    binary = b'\x7fELF\x02\x01junk\x00__version__ = "3.1.4"\x00usage: tool [--version] [--help]\x00\xff\xfe\xfd'
    (bundled_files / "tool.bin").write_bytes(binary)
    recipe.declares("local_bin", "tool", source="tool.bin")

    report = totchef.up()

    report.assert_shows("local_bin.tool", "applied")
    assert "local_bin.tool,absent,3.1.4,3.1.4,applied" in report.full_table
    assert (home / ".local/bin/tool").read_bytes() == binary  # installed verbatim, bytes untouched


def test_5_4_4_usr_local_bin_is_always_root_local_bin_is_user_scoped(cli):
    """`usr_local_bin` lists as a root cook (its domain is /usr/local/bin); `local_bin` stays user-scoped."""
    cli.run("--list-cooks").assert_lists("usr_local_bin", scope="root")
    cli.run("--list-cooks").assert_lists("local_bin", scope="user")


def test_5_4_5_source_defaults_to_the_bundled_command_named_after_the_entry(recipe, home, bundled_files, totchef):
    """With no `source`, the entry installs the unique bundled command whose stem matches the entry name — `[local_bin.tool]` needs no keys at all."""
    tool = '#!/bin/bash\n__version__="1.2.0"\ncase "$1" in --version) echo "$__version__";; --help) echo "usage: tool";; esac\n'
    (bundled_files / "tool.sh").write_text(tool)
    recipe.declares("local_bin", "tool")

    report = totchef.up()

    report.assert_shows("local_bin.tool", "applied")
    assert "local_bin.tool,absent,1.2.0,1.2.0,applied" in report.full_table  # the resolved source passes the version contract
    assert (home / ".local/bin/tool").read_text() == tool  # command still named after the resolved stem


def test_5_4_6_usr_local_sbin_installs_admin_commands_always_as_root(recipe, usr_local_sbin_dir, bundled_files, totchef, cli):
    """`[usr_local_sbin.<name>]` installs to /usr/local/sbin — admin and daemon helpers, outside ordinary users' PATH — always as root, under the same version contract."""
    helper = '#!/bin/bash\n__version__="1.0.0"\ncase "$1" in --version) echo "$__version__";; --help) echo "usage: helper";; esac\n'
    (bundled_files / "helper.sh").write_text(helper)
    recipe.declares("usr_local_sbin", "helper")

    totchef.up().assert_shows("usr_local_sbin.helper", "applied")

    installed = usr_local_sbin_dir / "helper"
    assert installed.read_text() == helper
    assert (installed.stat().st_mode & 0o777) == 0o755
    cli.run("--list-cooks").assert_lists("usr_local_sbin", scope="root")


# 5.5 Set specific lines in a config file


def test_5_5_1_conf_replaces_matching_lines_in_place_and_appends_missing_ones(recipe, totchef, tmp_path):
    """`[conf.<name>]` keys each declared line on the text before `=` (the whole line when there is none): a line with the same key is replaced in place, a missing one is appended, and every other line — comments included — is left untouched."""
    target = tmp_path / "nala.conf"
    target.write_text("[Nala]\n# full_upgrade = true is what we want\nfull_upgrade = false\nassume_yes = false\n")
    recipe.declares("conf", "nala", target=str(target), lines=["[Nala]", "full_upgrade = true", "update_show_packages = true"])

    totchef.up().assert_shows("conf.nala", "applied")

    assert target.read_text() == "[Nala]\n# full_upgrade = true is what we want\nfull_upgrade = true\nassume_yes = false\nupdate_show_packages = true\n"


def test_5_5_2_conf_creates_a_missing_target(recipe, totchef, tmp_path):
    """A missing `target` is created (parents included) holding exactly the declared lines."""
    target = tmp_path / "etc" / "fresh.conf"
    recipe.declares("conf", "fresh", target=str(target), lines=["[Nala]", "full_upgrade = true"])

    totchef.up().assert_shows("conf.fresh", "applied")

    assert target.read_text() == "[Nala]\nfull_upgrade = true\n"


def test_5_5_3_conf_rewrites_only_when_a_line_differs(recipe, terminal, totchef, tmp_path):
    """Diffed by content hash: a compliant file is never rewritten and a post_hook fires only on a real change."""
    target = tmp_path / "app.conf"
    target.write_text("mode = fast\n")
    recipe.declares("conf", "app", target=str(target), line="mode = fast", post_hook="reload-app")

    totchef.up().assert_shows("conf.app", "unchanged")
    terminal.expect_not_ran("reload-app")

    target.write_text("mode = slow\n")

    totchef.up().assert_shows("conf.app", "applied")
    terminal.expect_ran("reload-app")
    assert target.read_text() == "mode = fast\n"
