"""chef.main's privilege gate: a `just plan` dry-run skips ensure_root, a real apply calls it; surrounding I/O is stubbed so only the gating branch is exercised."""

import chef


def stub_main_io(monkeypatch):
    """Neutralize everything main does except the ensure_root gate, recording whether it would have escalated."""
    escalated = []
    monkeypatch.setattr(chef, "ensure_root", lambda: escalated.append(True))
    monkeypatch.setattr(chef, "start_logging", lambda: None)
    monkeypatch.setattr(chef, "drain_logs", lambda: None)
    monkeypatch.setattr(chef, "validate", lambda config: None)
    monkeypatch.setattr(chef, "run_recipe", lambda config, dry_run: {})
    monkeypatch.setattr(chef, "print_report", lambda results, dry_run: None)
    return escalated


def test_main_does_not_escalate_on_dry_run(monkeypatch):
    escalated = stub_main_io(monkeypatch)
    chef.main(dry_run=True, lint=False)
    assert escalated == []


def test_main_escalates_on_apply(monkeypatch):
    escalated = stub_main_io(monkeypatch)
    chef.main(dry_run=False, lint=False)
    assert escalated == [True]


def test_main_lint_skips_escalation(monkeypatch):
    escalated = stub_main_io(monkeypatch)
    chef.main(dry_run=False, lint=True)
    assert escalated == []
