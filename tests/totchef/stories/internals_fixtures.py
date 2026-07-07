"""White-box handles onto totchef internals, for scheduler/pump/terminal tests deliberately not black-box; keeps tests inside the CLI seam cerberus enforces."""

from typing import TYPE_CHECKING

import pytest
import totchef.cook_runner as cook_runner_module
import totchef.logs as logs_module
import totchef.terminal as terminal_module

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture
def log_internals() -> ModuleType:
    return logs_module


@pytest.fixture
def terminal_internals() -> ModuleType:
    return terminal_module


@pytest.fixture
def cook_runner_internals() -> ModuleType:
    return cook_runner_module
