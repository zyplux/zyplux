from unittest.mock import patch

import pytest
from config_to_kv.bootstrap import notify_workers
from config_to_kv.cloudflare import list_bootstrap_urls


def test_2_1_only_declared_bootstrap_endpoints_are_selected() -> None:
    assert list_bootstrap_urls([
        ("identity", []),
        ("email", [{"name": "BOOTSTRAP_URL", "text": "https://email.test/bootstrap"}]),
    ]) == ["https://email.test/bootstrap"]


def test_2_2_bootstrap_retries_only_config_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://github.test/token?run=1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")
    with (
        patch(
            "config_to_kv.bootstrap.request_https",
            side_effect=[(200, b'{"value":"signed-token"}'), (409, b""), (204, b"")],
        ) as request,
        patch("config_to_kv.bootstrap.sleep") as sleep,
    ):
        notify_workers(["https://email.test/bootstrap"], "revision")
    sleep.assert_called_once_with(5)
    assert request.call_args.args == (
        "https://email.test/bootstrap",
        {"Authorization": "Bearer signed-token", "X-Worker-Config-Revision": "revision"},
        "POST",
    )
    assert "audience=https%3A%2F%2Femail.test%2Fbootstrap" in request.call_args_list[0].args[0]


@pytest.mark.parametrize("status", [401, 404, 500, 302])
def test_2_3_bootstrap_failure_is_not_silently_skipped(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://github.test/token?run=1")
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "request-token")
    with (
        patch("config_to_kv.bootstrap.request_https", side_effect=[(200, b'{"value":"token"}'), (status, b"")]),
        pytest.raises(RuntimeError, match=f"HTTP {status}"),
    ):
        notify_workers(["https://email.test/bootstrap"], "revision")
