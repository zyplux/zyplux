from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

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
    assert result.findings == [ok("every pinned npm tool is at its newest quarantine-eligible release")]


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
            f"`jscpd` is pinned {npm_tool_pins['jscpd']} in {_PIN_SOURCE}, "
            "newest quarantine-eligible release is 99.0.0;"
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


def test_30_2_4_keeps_the_newest_mature_pin_while_the_latest_release_is_quarantined(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    ok: MakeFinding,
) -> None:
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    fake_registry.serve_npm(
        "fallow",
        "99.0.0",
        release_times={
            npm_tool_pins["fallow"]: "2000-01-01T00:00:00Z",
            "99.0.0": (datetime.now(UTC) - timedelta(hours=23)).isoformat(),
            "100.0.0-beta.1": "2000-01-01T00:00:00Z",
            "100.0.0": "2000-01-01T00:00:00Z",
        },
    )
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert result.findings == [ok("every pinned npm tool is at its newest quarantine-eligible release")]


@pytest.mark.parametrize("release_case", [(25, "99.0.0"), (23, "98.0.0")], ids=["latest_mature", "latest_quarantined"])
def test_30_2_5_requires_the_newest_eligible_pin(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    fail: MakeFinding,
    release_case: tuple[int, str],
) -> None:
    release_age, eligible_version = release_case
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    fake_registry.serve_npm(
        "fallow",
        "99.0.0",
        release_times={
            npm_tool_pins["fallow"]: "2000-01-01T00:00:00Z",
            "98.0.0": "2000-01-01T00:00:00Z",
            "99.0.0": (datetime.now(UTC) - timedelta(hours=release_age)).isoformat(),
        },
    )
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert result.findings == [
        fail(
            f"`fallow` is pinned {npm_tool_pins['fallow']} in {_PIN_SOURCE}, "
            f"newest quarantine-eligible release is {eligible_version};"
            " bump the pin and release cerberus"
        )
    ]


@pytest.mark.parametrize("release_time", ["invalid", "2999-01-01T00:00:00Z"])
def test_30_2_6_errors_when_release_times_are_invalid_or_no_release_is_eligible(
    run_check_with_files: RunCheckWithFiles,
    fake_registry: FakeRegistry,
    npm_tool_pins: dict[str, str],
    error: MakeFinding,
    release_time: str,
) -> None:
    _serve_all_pins_latest(fake_registry, npm_tool_pins)
    fake_registry.serve_npm("fallow", npm_tool_pins["fallow"], release_times={npm_tool_pins["fallow"]: release_time})
    result = run_check_with_files(CHECK_ID, _PIN_OWNER_FILES)
    assert len(result.findings) == 1
    assert result.findings[0].status == error("").status
    assert "could not determine the latest `fallow`" in result.findings[0].message
