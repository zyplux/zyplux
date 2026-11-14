(
    """User stories §4 — Language package-manager wrappers. One test per §4 criterion on """
    """the real chef in-process; system boundaries (bash, network, host) are faked, except """
    """the §4.3.3 landing-path story which runs in a container."""
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from act_fixtures import Totchef
    from arrange_fixtures import FakeHttp, FakeSystem, FakeTerminal, RecipeBuilder
    from container_fixtures import ContainerRun

PAIRED_PARTIES = 2


# 4.1 Install and update Rust crates


def test_4_1_1_cargo_installs_via_binstall(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
    """`[cargo]` installs via `cargo binstall` (one batched command that skips already-current crates)."""
    recipe.declares("cargo", packages=["ripgrep"])
    system.has("cargo", "cargo-binstall")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "")

    def _rearm_cargo_list_with_ripgrep() -> None:
        terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n    rg\n")

    terminal.arrange("cargo-binstall --no-confirm", effect=_rearm_cargo_list_with_ripgrep)

    report = totchef.up()

    report.assert_shows("cargo.ripgrep", "installed")
    terminal.expect_ran("cargo-binstall --no-confirm ripgrep")


def test_4_1_2_cargo_binstall_is_bootstrapped_once_if_missing(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
    """If cargo-binstall is missing, it's bootstrapped once via `cargo install`."""
    recipe.declares("cargo", packages=["ripgrep"])
    system.has("cargo")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "")

    def _bootstrap_cargo_binstall() -> None:
        system.has("cargo-binstall")

    def _rearm_cargo_list_with_ripgrep() -> None:
        terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n")

    terminal.arrange("cargo install cargo-binstall", effect=_bootstrap_cargo_binstall)
    terminal.arrange("cargo-binstall --no-confirm", effect=_rearm_cargo_list_with_ripgrep)

    report = totchef.up()

    report.assert_succeeded()
    assert terminal.count("cargo install cargo-binstall") == 1


def test_4_1_3_missing_cargo_fails_hard_pointing_at_url_rustup(
    recipe: RecipeBuilder, http: FakeHttp, totchef: Totchef
) -> None:
    """If cargo is missing the run fails hard, telling the operator the [url] rustup install must run first."""
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("rustup")


def test_4_1_4_latest_crate_versions_looked_up_concurrently(
    recipe: RecipeBuilder, http: FakeHttp, totchef: Totchef
) -> None:
    """Latest versions are looked up concurrently from crates.io for the plan."""
    recipe.declares("cargo", packages=["ripgrep", "just"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    http.arrange("crates.io/api/v1/crates/just", '{"crate": {"max_stable_version": "1.40.0"}}')
    http.expect_concurrent(parties=PAIRED_PARTIES)  # both crate lookups must be in flight together, not serialized

    plan = totchef.plan()

    plan.assert_shows("cargo.ripgrep", "would install")
    plan.assert_shows("cargo.just", "would install")
    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
    http.expect_fetched("crates.io/api/v1/crates/just")
    assert http.max_concurrent_requests == PAIRED_PARTIES  # the two crates.io fetches overlapped


def test_4_1_5_latest_version_probes_are_time_bounded(recipe: RecipeBuilder, http: FakeHttp, totchef: Totchef) -> None:
    (
        """Every crates.io probe passes a timeout, so a stalled registry connection fails """
        """fast to 'unknown latest' rather than wedging the thread pool and hanging the """
        """plan forever."""
    )
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    totchef.plan()

    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
    http.expect_bounded_timeouts()


# 4.2 Install and upgrade Python CLI tools


def test_4_2_1_uv_installs_and_upgrades_each_tool_concurrently(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
    """`[uv]` installs/upgrades each tool via uv, run concurrently behind uv's locks."""
    recipe.declares("uv", packages=["ruff", "pyright"])
    system.has("uv")
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/pyright/json", '{"info": {"version": "1.1.380"}}')
    terminal.arrange("uv tool list", "ruff v0.5.0\n")  # ruff present (upgrade), pyright absent (install)
    terminal.expect_concurrent(
        "uv tool upgrade", "uv tool install", parties=PAIRED_PARTIES
    )  # both tool actions run at once

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("uv tool upgrade ruff")
    terminal.expect_ran("uv tool install pyright")
    assert (
        terminal.max_concurrent_commands == PAIRED_PARTIES
    )  # the upgrade and the install ran concurrently, not one after the other


def test_4_2_2_uv_failure_reports_hard_naming_the_failed_tools(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
    """If any tool fails, the run reports a hard failure naming the failed tools."""
    recipe.declares("uv", packages=["ruff", "brokentool"])
    system.has("uv")
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/brokentool/json", '{"info": {"version": "1.0"}}')
    terminal.arrange("uv tool list", "")
    terminal.arrange("uv tool install brokentool", exit_code=1)

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("brokentool")


def test_4_2_3_uv_requires_uv_and_looks_up_latest_from_pypi(
    recipe: RecipeBuilder, http: FakeHttp, totchef: Totchef
) -> None:
    """Requires uv to be present; latest versions looked up concurrently from PyPI."""
    recipe.declares("uv", packages=["ruff", "pyright"])
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/pyright/json", '{"info": {"version": "1.1.380"}}')
    http.expect_concurrent(parties=PAIRED_PARTIES)  # both PyPI lookups must overlap

    plan = totchef.plan()

    plan.assert_shows("uv.ruff", "would install")
    http.expect_fetched("pypi.org/pypi/ruff/json")
    assert http.max_concurrent_requests == PAIRED_PARTIES  # the two PyPI fetches ran concurrently for the plan

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("[url]")


# 4.3 Install and upgrade global pnpm packages


PI = "@earendil-works/pi-coding-agent"


def _global_list(*installed: tuple[str, str]) -> str:
    (
        """What `pnpm list -g --depth 0 --json` prints for `installed` — the only reliable reader of """
        """pnpm's global tree, whose on-disk layout is a content-hashed directory."""
    )
    entries = ", ".join(f'"{name}": {{"version": "{version}"}}' for name, version in installed)
    return '[{"dependencies": {' + entries + "}}]"


def test_4_3_1_pnpm_installs_and_upgrades_each_global_package(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem
) -> None:
    (
        """`[pnpm]` installs missing globals and upgrades drifted ones via a single batched """
        """`pnpm add -g`; installed versions are read from pnpm's global tree."""
    )
    recipe.declares("pnpm", packages=[PI, "left-pad"])
    system.has("pnpm")
    # left-pad already installed at an older version → upgrade; PI absent → install
    terminal.arrange("pnpm list -g", _global_list(("left-pad", "1.2.0")))

    def _land_pnpm_globals() -> None:
        terminal.arrange("pnpm list -g", _global_list((PI, "0.75.5"), ("left-pad", "1.3.0")))

    terminal.arrange("pnpm add -g", effect=_land_pnpm_globals)

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("pnpm." + PI, "installed")  # absent → installed
    report.assert_shows("pnpm.left-pad", "upgraded")  # drifted → upgraded
    terminal.expect_ran("pnpm add -g --ignore-scripts " + PI + " left-pad")  # one batched command for both


def test_4_3_2_pnpm_requires_pnpm(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """Requires pnpm present (depends on the [url] pnpm installer)."""
    recipe.declares("pnpm", packages=[PI, "left-pad"])

    plan = totchef.plan()

    plan.assert_shows("pnpm." + PI, "would install")

    report = totchef.up()  # pnpm isn't installed → hard fail pointing at [url]

    report.assert_hard_failed()
    report.assert_logged("[url]")


def test_4_3_3_pnpm_installs_globals_into_pnpm_home_not_an_inherited_data_dir(
    apply_in_container: Callable[[str, list[str], dict[str, str] | None, dict[str, str] | None], ContainerRun],
) -> None:
    (
        """pnpm reads its global root from `$XDG_DATA_HOME` when left to itself, so a variable """
        """inherited from the pre-drop environment would strand globals outside the operator's """
        """home. The cook pins `PNPM_HOME` (and its bin dir on PATH) instead. In a container."""
    )
    run = apply_in_container(
        '[pnpm]\npackages = ["left-pad"]\n',
        ["/home/tester/.local/share/pnpm/global", "/home/tester/inherited-data/pnpm"],
        None,
        {"XDG_DATA_HOME": "/home/tester/inherited-data"},
    )

    assert run.owners["/home/tester/.local/share/pnpm/global"] == "tester", (
        run.transcript
    )  # landed in the operator's own pnpm home
    assert run.owners["/home/tester/inherited-data/pnpm"] is None, run.transcript  # never the inherited data dir


def test_4_3_4_pnpm_keeps_a_global_within_its_declared_major(
    recipe: RecipeBuilder, terminal: FakeTerminal, totchef: Totchef, system: FakeSystem
) -> None:
    """A package range such as node@26 refreshes within that range while reporting under the package name."""
    recipe.declares("pnpm", packages=["node@26"])
    system.has("pnpm")
    terminal.arrange("pnpm list -g", _global_list(("node", "26.6.0")))

    def install_node() -> None:
        terminal.arrange("pnpm list -g", _global_list(("node", "26.7.0")))

    terminal.arrange("pnpm add -g --ignore-scripts node@26", effect=install_node)

    report = totchef.up()

    report.assert_shows("pnpm.node", "upgraded")
    terminal.expect_ran("pnpm add -g --ignore-scripts node@26")


def test_4_3_5_pnpm_rejects_conflicting_specs_for_one_package(recipe: RecipeBuilder, totchef: Totchef) -> None:
    """Two specs for one package are ambiguous and fail instead of silently selecting the last one."""
    recipe.declares("pnpm", packages=["node@26", "node@27"])

    report = totchef.up()

    report.assert_rejected("node@26")
    report.assert_rejected("node@27")


def test_4_3_6_pnpm_delegates_release_age_resolution(
    recipe: RecipeBuilder, terminal: FakeTerminal, http: FakeHttp, totchef: Totchef, system: FakeSystem
) -> None:
    """pnpm owns which release is currently eligible under its minimumReleaseAge policy."""
    package = "@zyplux/cz"
    recipe.declares("pnpm", packages=[package])
    system.has("pnpm")
    terminal.arrange("pnpm list -g", _global_list((package, "0.7.0")))
    terminal.arrange("pnpm add -g")

    plan = totchef.plan()
    report = totchef.up()

    plan.assert_shows("pnpm." + package, "would sync")
    report.assert_shows("pnpm." + package, "unchanged")
    terminal.expect_ran("pnpm add -g --ignore-scripts " + package)
    assert http.requests == []
