"""User stories §4 — Language package-manager wrappers. One test per §4 criterion on the real chef in-process; system boundaries (bash, network, host) are faked, except the §4.3.3 landing-path story which runs in a container."""


# 4.1 Install and update Rust crates


def test_4_1_1_cargo_installs_via_binstall(recipe, terminal, http, totchef, system):
    """`[cargo]` installs via `cargo binstall` (one batched command that skips already-current crates)."""
    recipe.declares("cargo", packages=["ripgrep"])
    system.has("cargo", "cargo-binstall")
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    terminal.arrange("cargo install --list", "")
    terminal.arrange("cargo-binstall --no-confirm", effect=lambda: terminal.arrange("cargo install --list", "ripgrep v14.1.1:\n    rg\n"))

    report = totchef.up()

    report.assert_shows("cargo.ripgrep", "installed")
    terminal.expect_ran("cargo-binstall --no-confirm ripgrep")


def test_4_1_2_cargo_binstall_is_bootstrapped_once_if_missing(recipe, terminal, http, totchef, system):
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


def test_4_1_3_missing_cargo_fails_hard_pointing_at_url_rustup(recipe, http, totchef):
    """If cargo is missing the run fails hard, telling the operator the [url] rustup install must run first."""
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("rustup")


def test_4_1_4_latest_crate_versions_looked_up_concurrently(recipe, http, totchef):
    """Latest versions are looked up concurrently from crates.io for the plan."""
    recipe.declares("cargo", packages=["ripgrep", "just"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')
    http.arrange("crates.io/api/v1/crates/just", '{"crate": {"max_stable_version": "1.40.0"}}')
    http.expect_concurrent(parties=2)  # both crate lookups must be in flight together, not serialized

    plan = totchef.plan()

    plan.assert_shows("cargo.ripgrep", "would install")
    plan.assert_shows("cargo.just", "would install")
    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
    http.expect_fetched("crates.io/api/v1/crates/just")
    assert http.max_concurrent_requests == 2  # the two crates.io fetches overlapped


def test_4_1_5_latest_version_probes_are_time_bounded(recipe, http, totchef):
    """Every crates.io probe passes a timeout, so a stalled registry connection fails fast to 'unknown latest' rather than wedging the thread pool and hanging the plan forever."""
    recipe.declares("cargo", packages=["ripgrep"])
    http.arrange("crates.io/api/v1/crates/ripgrep", '{"crate": {"max_stable_version": "14.1.1"}}')

    totchef.plan()

    http.expect_fetched("crates.io/api/v1/crates/ripgrep")
    http.expect_bounded_timeouts()


# 4.2 Install and upgrade Python CLI tools


def test_4_2_1_uv_installs_and_upgrades_each_tool_concurrently(recipe, terminal, http, totchef, system):
    """`[uv]` installs/upgrades each tool via uv, run concurrently behind uv's locks."""
    recipe.declares("uv", packages=["ruff", "pyright"])
    system.has("uv")
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/pyright/json", '{"info": {"version": "1.1.380"}}')
    terminal.arrange("uv tool list", "ruff v0.5.0\n")  # ruff present (upgrade), pyright absent (install)
    terminal.expect_concurrent("uv tool upgrade", "uv tool install", parties=2)  # both tool actions run at once

    report = totchef.up()

    report.assert_succeeded()
    terminal.expect_ran("uv tool upgrade ruff")
    terminal.expect_ran("uv tool install pyright")
    assert terminal.max_concurrent_commands == 2  # the upgrade and the install ran concurrently, not one after the other


def test_4_2_2_uv_failure_reports_hard_naming_the_failed_tools(recipe, terminal, http, totchef, system):
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


def test_4_2_3_uv_requires_uv_and_looks_up_latest_from_pypi(recipe, http, totchef):
    """Requires uv to be present; latest versions looked up concurrently from PyPI."""
    recipe.declares("uv", packages=["ruff", "pyright"])
    http.arrange("pypi.org/pypi/ruff/json", '{"info": {"version": "0.6.0"}}')
    http.arrange("pypi.org/pypi/pyright/json", '{"info": {"version": "1.1.380"}}')
    http.expect_concurrent(parties=2)  # both PyPI lookups must overlap

    plan = totchef.plan()

    plan.assert_shows("uv.ruff", "would install")
    http.expect_fetched("pypi.org/pypi/ruff/json")
    assert http.max_concurrent_requests == 2  # the two PyPI fetches ran concurrently for the plan

    report = totchef.up()

    report.assert_hard_failed()
    report.assert_logged("[url]")


# 4.3 Install and upgrade global bun packages


PI = "@earendil-works/pi-coding-agent"


def _bun_global(home, name: str, version: str):
    """An effect that simulates `bun add -g` landing `name` in bun's global tree at `version`, so the cook's filesystem re-probe sees it installed."""
    pkg_dir = home / ".bun/install/global/node_modules" / name

    def install() -> None:
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "package.json").write_text('{"version": "' + version + '"}')

    return install


def test_4_3_1_bun_installs_and_upgrades_each_global_package(recipe, terminal, http, totchef, system, home):
    """`[bun]` installs missing globals and upgrades drifted ones via a single batched `bun add -g`; installed versions are read from bun's global tree."""
    recipe.declares("bun", packages=[PI, "left-pad"])
    system.has("bun")
    http.arrange("registry.npmjs.org/" + PI, '{"dist-tags": {"latest": "0.75.5"}}')
    http.arrange("registry.npmjs.org/left-pad", '{"dist-tags": {"latest": "1.3.0"}}')
    _bun_global(home, "left-pad", "1.2.0")()  # left-pad already installed at an older version → upgrade
    terminal.arrange("bun add -g", effect=lambda: (_bun_global(home, PI, "0.75.5")(), _bun_global(home, "left-pad", "1.3.0")()))

    report = totchef.up()

    report.assert_succeeded()
    report.assert_shows("bun." + PI, "installed")  # absent → installed
    report.assert_shows("bun.left-pad", "upgraded")  # drifted → upgraded
    terminal.expect_ran("bun add -g --ignore-scripts " + PI + " left-pad")  # one batched command for both


def test_4_3_2_bun_requires_bun_and_looks_up_latest_from_the_npm_registry(recipe, http, totchef):
    """Requires bun present (depends on the [url] bun installer); latest versions are looked up concurrently from the npm registry."""
    recipe.declares("bun", packages=[PI, "left-pad"])
    http.arrange("registry.npmjs.org/" + PI, '{"dist-tags": {"latest": "0.75.5"}}')
    http.arrange("registry.npmjs.org/left-pad", '{"dist-tags": {"latest": "1.3.0"}}')
    http.expect_concurrent(parties=2)  # both npm lookups must overlap, not serialize

    plan = totchef.plan()

    plan.assert_shows("bun." + PI, "would install")
    http.expect_fetched("registry.npmjs.org/left-pad")
    assert http.max_concurrent_requests == 2  # the two npm fetches ran concurrently for the plan

    report = totchef.up()  # bun isn't installed → hard fail pointing at [url]

    report.assert_hard_failed()
    report.assert_logged("[url]")


def test_4_3_3_bun_installs_globals_into_bun_home_not_the_cache_dir(apply_in_container):
    """The cook pins `BUN_INSTALL` to bun's home, so a global lands in `~/.bun` (on PATH) and never the `$XDG_CACHE_HOME/.bun` dir bun would otherwise pick under the privilege drop. In a container."""
    run = apply_in_container(
        '[bun]\npackages = ["left-pad"]\n',
        ["/home/tester/.bun/install/global/node_modules/left-pad", "/home/tester/.cache/.bun/install/global/node_modules/left-pad"],
    )

    assert run.owners["/home/tester/.bun/install/global/node_modules/left-pad"] == "tester", run.transcript  # landed where PATH sees it
    assert run.owners["/home/tester/.cache/.bun/install/global/node_modules/left-pad"] is None, run.transcript  # never the cache dir


def test_4_3_4_bun_links_node_to_its_runtime_so_node_shebang_globals_run(recipe, terminal, http, totchef, system, home):
    """A node CLI's `#!/usr/bin/env node` shebang (left intact by `bun add -g`) needs a `node` on PATH; the cook drops a `node` symlink to bun in bun's bin dir so it resolves and runs node-compatibly. Best-effort and idempotent — it runs every sync, so a converged re-run with nothing to install still restores the runtime if removed."""
    recipe.declares("bun", packages=[PI])
    system.has("bun")
    http.arrange("registry.npmjs.org/" + PI, '{"dist-tags": {"latest": "0.75.5"}}')
    terminal.arrange("bun add -g", effect=lambda: _bun_global(home, PI, "0.75.5")())

    node = home / ".bun/bin/node"
    bun = system.bin_dir / "bun"

    totchef.up().assert_succeeded()  # absent → installed; the node runtime is linked alongside
    assert node.is_symlink() and node.resolve() == bun.resolve()

    node.unlink()  # runtime removed out of band
    totchef.up().assert_succeeded()  # converged: nothing to install, yet the runtime is restored
    assert node.is_symlink() and node.resolve() == bun.resolve()
