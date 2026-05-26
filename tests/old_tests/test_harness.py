"""become_user, the single privilege-drop chokepoint: root on a real `just up`, an early no-op on an unprivileged dry-run; fakes stand in for the syscalls."""

import pytest

from totchef import harness


def test_become_user_is_a_noop_when_already_unprivileged(monkeypatch):
    monkeypatch.setattr(harness.os, "geteuid", lambda: 1000)
    monkeypatch.delenv("SUDO_USER", raising=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("become_user must not drop privilege when non-root")

    monkeypatch.setattr(harness.os, "setgid", forbidden)
    monkeypatch.setattr(harness.os, "setuid", forbidden)
    monkeypatch.setattr(harness.os, "initgroups", forbidden)

    assert harness.become_user() is None


def test_become_user_exits_when_root_without_sudo(monkeypatch):
    monkeypatch.setattr(harness.os, "geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_USER", raising=False)

    with pytest.raises(SystemExit):
        harness.become_user()
