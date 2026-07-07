"""White-box handles onto totchef's own internals, for the scheduler/pump/terminal-rendering tests that are deliberately not black-box (see test_8_observing_a_run.py's module docstring). A story test takes these as fixtures rather than importing the modules directly, so it stays inside the CLI seam cerberus's cli-py-tests check enforces."""

from types import ModuleType

import pytest
import totchef.cook_runner as cook_runner_module
import totchef.logs as logs_module
import totchef.terminal as terminal_module


@pytest.fixture
def log_internals() -> ModuleType:
    return logs_module


@pytest.fixture
def terminal_internals() -> ModuleType:
    return terminal_module


@pytest.fixture
def cook_runner_internals() -> ModuleType:
    return cook_runner_module
