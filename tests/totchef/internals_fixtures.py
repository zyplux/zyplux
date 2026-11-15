(
    """White-box handles onto totchef internals, for scheduler/pump/terminal tests deliberately """
    """not black-box; keeps tests inside the CLI seam cerberus enforces."""
)

from typing import TYPE_CHECKING

import pytest
import totchef.cook_runner as cook_runner_module
import totchef.log_pump as log_pump_module
import totchef.logs as logs_module
import totchef.terminal as terminal_module

if TYPE_CHECKING:
    from types import ModuleType

    from arrange_fixtures import FakeHost


@pytest.fixture
def log_internals(_isolated_host: FakeHost) -> ModuleType:
    return logs_module


@pytest.fixture
def log_pump(_isolated_host: FakeHost) -> ModuleType:
    return log_pump_module


@pytest.fixture
def terminal_internals(_isolated_host: FakeHost) -> ModuleType:
    return terminal_module


@pytest.fixture
def cook_runner_internals(_isolated_host: FakeHost) -> ModuleType:
    return cook_runner_module
