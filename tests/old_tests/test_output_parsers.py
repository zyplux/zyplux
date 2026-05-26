"""Pure parsers over external CLI output, pinning the column/format assumptions that break silently (a mis-read version, not a crash) when a tool reformats."""

from totchef.cooks.apt_pkg_root_cook import parse_policy
from totchef.cooks.cargo_cook import parse_crate_list, parse_crates_latest
from totchef.cooks.snap_root_cook import parse_refresh_list, parse_snap_list
from totchef.cooks.url_cook import parse_version
from totchef.cooks.uv_cook import parse_pypi_latest, parse_tool_list

# --- parse_snap_list ---

SNAP_LIST = "\n".join(
    [
        "Name      Version        Rev    Tracking       Publisher   Notes",
        "core22    20240111       1122   latest/stable  canonical   base",
        "firefox   122.0-2        3600   latest/stable  mozilla     -",
        "chromium  121.0.6167.85  2805   latest/stable  canonical   -",
    ]
)


def test_parse_snap_list_maps_name_to_version():
    assert parse_snap_list(SNAP_LIST) == {
        "core22": "20240111",
        "firefox": "122.0-2",
        "chromium": "121.0.6167.85",
    }


def test_parse_snap_list_skips_header_and_blank_lines():
    assert parse_snap_list("Name  Version\n\n") == {}


def test_parse_snap_list_nameless_line_is_unknown_version():
    assert parse_snap_list("loner\n") == {"loner": "unknown"}


# --- parse_refresh_list ---

REFRESH_LIST = "\n".join(
    [
        "Name         Version        Rev   Size   Publisher    Notes",
        "thunderbird  140.11.0esr-1  1117  239MB  canonical**  -",
        "chromium     148.0.7778.99  2999  180MB  canonical**  -",
    ]
)


def test_parse_refresh_list_maps_name_to_available_version():
    assert parse_refresh_list(REFRESH_LIST) == {
        "thunderbird": "140.11.0esr-1",
        "chromium": "148.0.7778.99",
    }


def test_parse_refresh_list_ignores_all_up_to_date_message():
    # No header line => nothing is a row, so the message isn't misread as a snap.
    assert parse_refresh_list("All snaps up to date.\n") == {}


# --- parse_version (vendor --version output) ---


def test_parse_version_extracts_dotted_version_from_varied_formats():
    assert parse_version("rustup 1.29.0 (28d1352db 2026-03-05)") == "1.29.0"
    assert parse_version("uv 0.11.16 (x86_64-unknown-linux-gnu)") == "0.11.16"
    assert parse_version("1.3.14") == "1.3.14"
    assert parse_version("2.1.150 (Claude Code)") == "2.1.150"


def test_parse_version_falls_back_to_present_without_a_match():
    assert parse_version("some banner with no number") == "present"


# --- parse_pypi_latest / parse_crates_latest (HTTP JSON bodies) ---


def test_parse_pypi_latest_reads_info_version():
    assert parse_pypi_latest(b'{"info": {"version": "0.15.14"}}') == "0.15.14"


def test_parse_crates_latest_prefers_max_stable_over_newest():
    body = b'{"crate": {"max_stable_version": "1.51.0", "newest_version": "1.52.0-rc.1"}}'
    assert parse_crates_latest(body) == "1.51.0"


def test_parse_crates_latest_falls_back_to_newest_when_no_stable():
    body = b'{"crate": {"max_stable_version": null, "newest_version": "0.1.0-beta"}}'
    assert parse_crates_latest(body) == "0.1.0-beta"


# --- parse_crate_list ---

CARGO_LIST = "\n".join(
    [
        "cargo-binstall v1.6.4:",
        "    cargo-binstall",
        "just v1.24.0:",
        "    just",
        "rumdl v0.2.0:",
        "    rumdl",
    ]
)


def test_parse_crate_list_maps_name_to_version_stripping_v():
    assert parse_crate_list(CARGO_LIST) == {
        "cargo-binstall": "1.6.4",
        "just": "1.24.0",
        "rumdl": "0.2.0",
    }


def test_parse_crate_list_skips_indented_binary_lines():
    # The indented `    just` binary line must not be read as its own crate.
    assert parse_crate_list("just v1.0.0:\n    just\n") == {"just": "1.0.0"}


# --- parse_tool_list ---

UV_LIST = "\n".join(
    [
        "ruff v0.4.2",
        "- ruff",
        "pyright v1.1.360",
        "- pyright",
    ]
)


def test_parse_tool_list_maps_name_to_version_stripping_v():
    assert parse_tool_list(UV_LIST) == {"ruff": "0.4.2", "pyright": "1.1.360"}


def test_parse_tool_list_skips_dash_prefixed_binary_lines():
    assert parse_tool_list("- orphan\nruff v0.4.2\n- ruff\n") == {"ruff": "0.4.2"}


# --- parse_policy (the apt-cache policy state machine) ---

NALA_POLICY = "\n".join(
    [
        "nala:",
        "  Installed: 0.14.0",
        "  Candidate: 0.14.0",
        "  Version table:",
        " *** 0.14.0 900",
        "        900 http://archive.ubuntu.com/ubuntu noble/universe amd64 Packages",
        "        100 /var/lib/dpkg/status",
    ]
)

MISSING_POLICY = "\n".join(
    [
        "ghost:",
        "  Installed: (none)",
        "  Candidate: (none)",
        "  Version table:",
    ]
)

BRAVE_POLICY = "\n".join(
    [
        "brave-browser:",
        "  Installed: 1.62.153",
        "  Candidate: 1.63.165",
        "  Version table:",
        "     1.63.165 500",
        "        500 https://brave-browser-apt-release.s3.brave.com stable/main amd64 Packages",
        " *** 1.62.153 100",
        "        100 /var/lib/dpkg/status",
    ]
)


def test_parse_policy_single_repo_package():
    assert parse_policy("nala", NALA_POLICY) == {
        "package": "nala",
        "installed": "0.14.0",
        "candidate": "0.14.0",
        "priority": 900,
        "source": "archive.ubuntu.com",
    }


def test_parse_policy_missing_package_has_priority_zero():
    # priority 0 + candidate "(none)" is exactly what makes apt_pkg.sync fail fast.
    row = parse_policy("ghost", MISSING_POLICY)
    assert row["candidate"] == "(none)"
    assert row["priority"] == 0
    assert row["source"] == ""


def test_parse_policy_reads_from_candidate_block_not_installed_line():
    # Candidate (1.63) differs from installed (1.62); priority + source must come
    # from the candidate's version block, not the *** installed line below it, and
    # the /var/lib/dpkg/status pseudo-source must be ignored.
    row = parse_policy("brave-browser", BRAVE_POLICY)
    assert row["installed"] == "1.62.153"
    assert row["candidate"] == "1.63.165"
    assert row["priority"] == 500
    assert row["source"] == "brave-browser-apt-release.s3.brave.com"
