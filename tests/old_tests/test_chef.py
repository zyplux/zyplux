"""apply()'s privilege gate: a `plan` dry-run skips ensure_root, a real apply calls it; surrounding I/O is stubbed so only the gating branch is exercised."""

from pathlib import Path

from totchef import cli


def stub_apply_io(monkeypatch):
    """Neutralize everything apply does except the ensure_root gate, recording whether it would have escalated."""
    escalated = []
    monkeypatch.setattr(cli, "ensure_root", lambda recipe_path: escalated.append(True))
    monkeypatch.setattr(cli, "start_logging", lambda echo_to_terminal=True: None)
    monkeypatch.setattr(cli, "drain_logs", lambda: None)
    monkeypatch.setattr(cli, "set_terminal_echo", lambda enabled: None)
    monkeypatch.setattr(cli, "load_recipe", lambda recipe_path: {})
    monkeypatch.setattr(cli, "validate", lambda config: None)
    monkeypatch.setattr(cli, "preview_plan", lambda config: None)
    monkeypatch.setattr(cli, "run_recipe", lambda config, dry_run: {})
    monkeypatch.setattr(cli, "print_report", lambda results, dry_run, title="Report", elapsed=None: None)
    return escalated


def test_apply_does_not_escalate_on_dry_run(monkeypatch):
    escalated = stub_apply_io(monkeypatch)
    cli.apply(Path("recipe.toml"), dry_run=True)
    assert escalated == []


def test_apply_escalates_on_real_run(monkeypatch):
    escalated = stub_apply_io(monkeypatch)
    cli.apply(Path("recipe.toml"), dry_run=False)
    assert escalated == [True]
