"""Fixtures for the prose-style tests, by role (arrange/act/assert); only system boundaries (bash, network, `$HOME`, host) are mocked."""

from act_fixtures import chef, cli, totchef
from arrange_fixtures import (
    apt_keyrings_dir,
    apt_sources_dir,
    bundled_files,
    chezmoi_cook,
    chezmoi_repo,
    custom_cooks,
    fresh_registry,
    fresh_runner_colors,
    home,
    http,
    recipe,
    register_plugin,
    scenario,
    system,
    terminal,
    totchef_version,
    usr_local_bin_dir,
    usr_local_sbin_dir,
)
from assert_fixtures import read_json
from container_fixtures import apply_in_container, container_image
from internals_fixtures import cook_runner_internals, log_internals, terminal_internals

__all__ = [
    "apply_in_container",
    "apt_keyrings_dir",
    "apt_sources_dir",
    "bundled_files",
    "chef",
    "chezmoi_cook",
    "chezmoi_repo",
    "cli",
    "container_image",
    "cook_runner_internals",
    "custom_cooks",
    "fresh_registry",
    "fresh_runner_colors",
    "home",
    "http",
    "log_internals",
    "read_json",
    "recipe",
    "register_plugin",
    "scenario",
    "system",
    "terminal",
    "terminal_internals",
    "totchef",
    "totchef_version",
    "usr_local_bin_dir",
    "usr_local_sbin_dir",
]
