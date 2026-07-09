from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seam_fixtures import FakeRegistry, MakeFinding, RunCheckWithFiles

CHECK_ID = "tool_pins_latest"

_PIN_SOURCE = "apps/cerberus/src/cerberus/tool_pins.py"
_PIN_OWNER_FILES = {_PIN_SOURCE: "", "package.json": "{}"}


def _serve_all_pins_latest(fake_registry: FakeRegistry, npm_tool_pins: dict[str, str]) -> None:
    for tool, pinned in npm_tool_pins.items():
        fake_registry.serve_npm(tool, pinned)


def test_30_1_1_skips_a_repo_that_does_not_carry_the_cerberus_tool_pins_source(
    run_check_with_files: RunCheckWithFiles, fake_registry: FakeRegistry, skip: MakeFinding
) -> None:
    result = run_check_with_files(CHECK_ID, {"package.json": "{}"})
    assert result.findings == [skip("no cerberus tool pins source in the repo")]
    assert fake_registry.requests == []


def test_30_2_1_passes_when_every_pinned_tool_is_at_its_latest_npm_release(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    ok: MakeFinding,
) -> None:
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert result.findings == [ok("every pinned npm tool is at its latest release")]


def test_30_2_2_fails_naming_the_tool_versions_and_pin_location_when_a_pin_lags(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    fail: MakeFinding,
) -> None:
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    fake_registry.serve_npm("jscpd", "99.0.0")
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert result.findings == [
        fail(
            f"`jscpd` is pinned {npm_tool_pins['jscpd']} in {_PIN_SOURCE}, npm latest is 99.0.0;"
            " bump the pin and release cerberus",
        )
    ]


def test_30_2_3_errors_instead_of_passing_when_the_npm_lookup_fails(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    error: MakeFinding,
) -> None:
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    fake_registry.payloads.pop(("registry.npmjs.org", "/jscpd"))
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert result.findings == [
        error("could not determine the latest `jscpd`: https://registry.npmjs.org/jscpd: connection refused")
    ]
